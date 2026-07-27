# SPDX-License-Identifier: LicenseRef-Blockscout
defmodule BlockScoutWeb.CSPHeader do
  @moduledoc """
  Plug to set content-security-policy with websocket endpoints
  """

  alias Phoenix.Controller
  alias Plug.Conn

  def init(opts), do: opts

  def call(conn, _opts) do
    config = Application.get_env(:block_scout_web, __MODULE__)
    google_url = "https://www.google.com"
    czilladx_url = "https://request-global.czilladx.com"
    coinzillatag_url = "https://coinzillatag.com"
    trustwallet_url = "https://raw.githubusercontent.com/trustwallet/assets/"
    walletconnect_urls =
      "https://rpc.walletconnect.com https://rpc.walletconnect.org https://relay.walletconnect.com " <>
        "https://relay.walletconnect.org wss://relay.walletconnect.com wss://relay.walletconnect.org " <>
        "https://pulse.walletconnect.com https://pulse.walletconnect.org https://api.web3modal.com " <>
        "https://api.web3modal.org https://keys.walletconnect.com https://keys.walletconnect.org " <>
        "https://notify.walletconnect.com https://notify.walletconnect.org https://echo.walletconnect.com " <>
        "https://echo.walletconnect.org https://push.walletconnect.com https://push.walletconnect.org " <>
        "wss://www.walletlink.org https://cca-lite.coinbase.com"
    walletconnect_frames = "https://verify.walletconnect.com https://verify.walletconnect.org"
    json_rpc_url = Application.get_env(:block_scout_web, :json_rpc)

    Controller.put_secure_browser_headers(conn, %{
      "content-security-policy" => "\
        connect-src 'self' #{json_rpc_url} #{config[:mixpanel_url]} #{config[:amplitude_url]} #{websocket_endpoints(conn)} #{czilladx_url} #{trustwallet_url} #{walletconnect_urls};\
        default-src 'self';\
        script-src 'self' 'unsafe-inline' 'unsafe-eval' #{coinzillatag_url} #{google_url} https://www.gstatic.com;\
        style-src 'self' 'unsafe-inline' 'unsafe-eval' https://fonts.googleapis.com;\
        img-src 'self' * data:;\
        media-src 'self' * data:;\
        font-src 'self' 'unsafe-inline' 'unsafe-eval' https://fonts.gstatic.com https://fonts.reown.com data:;\
        frame-src 'self' 'unsafe-inline' 'unsafe-eval' #{czilladx_url} #{google_url} #{walletconnect_frames};\
      "
    })
  end

  defp websocket_endpoints(conn) do
    host = Conn.get_req_header(conn, "host")
    "ws://#{host} wss://#{host}"
  end
end
