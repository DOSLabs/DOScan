# SPDX-License-Identifier: LicenseRef-Blockscout
defmodule NFTMediaHandlerTest do
  use ExUnit.Case, async: false

  alias Explorer.Chain.Token.Instance.Thumbnails

  setup_all do
    for app <- [:httpoison, :ex_aws, :image, :xav] do
      {:ok, _started} = Application.ensure_all_started(app)
    end

    :ok
  end

  defmodule HTTPServer do
    def start(response_body, response_content_type, owner) do
      {:ok, socket} =
        :gen_tcp.listen(0, [:binary, packet: :raw, active: false, reuseaddr: true])

      {:ok, port} = :inet.port(socket)
      pid = spawn_link(fn -> accept(socket, response_body, response_content_type, owner) end)
      {socket, pid, port}
    end

    defp accept(socket, response_body, response_content_type, owner) do
      case :gen_tcp.accept(socket) do
        {:ok, client} ->
          spawn_link(fn -> respond(client, response_body, response_content_type, owner) end)
          accept(socket, response_body, response_content_type, owner)

        {:error, :closed} ->
          :ok
      end
    end

    defp respond(client, response_body, response_content_type, owner) do
      {:ok, request} = receive_request(client, "")
      [request_line | _headers] = String.split(request, "\r\n")
      [method, path | _rest] = String.split(request_line, " ")

      case method do
        "GET" ->
          send_response(client, response_content_type, response_body)

        "PUT" ->
          send(owner, {:uploaded, path})
          send_response(client, "application/xml", "")
      end

      :gen_tcp.close(client)
    end

    defp receive_request(client, acc) do
      if String.contains?(acc, "\r\n\r\n") do
        {:ok, acc}
      else
        case :gen_tcp.recv(client, 0, 5_000) do
          {:ok, chunk} -> receive_request(client, acc <> chunk)
          error -> error
        end
      end
    end

    defp send_response(client, content_type, body) do
      response = [
        "HTTP/1.1 200 OK\r\n",
        "Content-Type: ",
        content_type,
        "\r\n",
        "Content-Length: ",
        Integer.to_string(byte_size(body)),
        "\r\n",
        "Connection: close\r\n\r\n",
        body
      ]

      :gen_tcp.send(client, response)
    end
  end

  setup do
    previous_ex_aws = Application.get_env(:ex_aws, :s3)
    previous_access_key = Application.get_env(:ex_aws, :access_key_id)
    previous_secret_key = Application.get_env(:ex_aws, :secret_access_key)
    previous_tmp_dir = Application.get_env(:nft_media_handler, :tmp_dir)

    on_exit(fn ->
      restore_env(:ex_aws, :s3, previous_ex_aws)
      restore_env(:ex_aws, :access_key_id, previous_access_key)
      restore_env(:ex_aws, :secret_access_key, previous_secret_key)
      restore_env(:nft_media_handler, :tmp_dir, previous_tmp_dir)
    end)
  end

  test "video processing reports only uploaded JPEG thumbnails" do
    fixture_path = Path.join([__DIR__, "fixtures", "video.mp4.b64"])
    video = fixture_path |> File.read!() |> Base.decode64!(ignore: :whitespace)
    {socket, _server_pid, port} = HTTPServer.start(video, "video/mp4", self())

    on_exit(fn -> :gen_tcp.close(socket) end)

    Application.put_env(:ex_aws, :access_key_id, "test-access-key")
    Application.put_env(:ex_aws, :secret_access_key, "test-secret-key")

    Application.put_env(:ex_aws, :s3,
      scheme: "http://",
      host: "127.0.0.1",
      port: port,
      region: "us-east-1",
      bucket_name: "test-bucket"
    )

    Application.put_env(:nft_media_handler, :tmp_dir, System.tmp_dir!() <> "/")

    url = "http://127.0.0.1:#{port}/probe.mp4"

    assert {[
              "/testnet/nft-media/" <> file_pattern,
              uploaded_sizes,
              false
            ], {"video", "mp4"}} =
             NFTMediaHandler.prepare_and_upload_by_url(url, "/testnet/nft-media")

    assert file_pattern =~ "{}.jpg"
    assert Enum.sort(uploaded_sizes) == [60, 250, 500]

    uploaded_paths =
      for _ <- uploaded_sizes do
        assert_receive {:uploaded, path}, 5_000
        path
      end

    assert Enum.all?(uploaded_paths, &String.ends_with?(&1, ".jpg"))
    refute Enum.any?(uploaded_paths, &String.contains?(&1, "original"))
  end

  test "image processing reports and uploads the original object" do
    fixture_path = Path.join([__DIR__, "fixtures", "image.png.b64"])
    image = fixture_path |> File.read!() |> Base.decode64!(ignore: :whitespace)
    {socket, _server_pid, port} = HTTPServer.start(image, "image/png", self())

    on_exit(fn -> :gen_tcp.close(socket) end)

    Application.put_env(:ex_aws, :access_key_id, "test-access-key")
    Application.put_env(:ex_aws, :secret_access_key, "test-secret-key")

    Application.put_env(:ex_aws, :s3,
      scheme: "http://",
      host: "127.0.0.1",
      port: port,
      region: "us-east-1",
      bucket_name: "test-bucket"
    )

    url = "http://127.0.0.1:#{port}/probe.png"

    assert {[
              "/testnet/nft-media/" <> file_pattern,
              uploaded_sizes,
              true
            ], {"image", "png"}} =
             NFTMediaHandler.prepare_and_upload_by_url(url, "/testnet/nft-media")

    assert file_pattern =~ "{}.png"
    assert uploaded_sizes == []

    uploaded_paths =
      for _ <- 1..(length(uploaded_sizes) + 1) do
        assert_receive {:uploaded, path}, 5_000
        path
      end

    assert Enum.all?(uploaded_paths, &String.ends_with?(&1, ".png"))
    assert Enum.count(uploaded_paths, &String.contains?(&1, "original")) == 1
  end

  test "thumbnail URL loading omits missing video originals and preserves image originals" do
    Application.put_env(:ex_aws, :s3, public_r2_url: "https://cdn.example/nft-media")

    assert {:ok, video_thumbnails} =
             Thumbnails.load(["/video/frame_{}.jpg", [60, 250, 500], false])

    refute Map.has_key?(video_thumbnails, "original")

    assert {:ok, image_thumbnails} =
             Thumbnails.load(["/image/file_{}.png", [60], true])

    assert image_thumbnails["original"] ==
             "https://cdn.example/nft-media/image/file_original.png"
  end

  defp restore_env(app, key, nil), do: Application.delete_env(app, key)
  defp restore_env(app, key, value), do: Application.put_env(app, key, value)
end
