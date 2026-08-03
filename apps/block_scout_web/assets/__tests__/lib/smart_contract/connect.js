/** @jest-environment jsdom */

const mockCreateAppKit = jest.fn()
const mockWeb3 = jest.fn()

jest.mock('@reown/appkit', () => ({
  createAppKit: (...args) => mockCreateAppKit(...args)
}))

jest.mock('@reown/appkit-adapter-ethers', () => ({
  EthersAdapter: jest.fn()
}))

jest.mock('web3', () => ({
  __esModule: true,
  default: (...args) => mockWeb3(...args)
}))

jest.mock('../../../js/lib/smart_contract/common_helpers', () => ({
  compareChainIDs: jest.fn(() => Promise.resolve()),
  formatError: jest.fn(),
  showConnectElements: jest.fn(),
  showConnectedToElements: jest.fn()
}))

jest.mock('../../../js/lib/modals', () => ({
  openWarningModal: jest.fn()
}))

const loadConnect = () => {
  jest.resetModules()
  document.body.innerHTML = `
    <input id="js-chain-id" value="43114">
    <input id="js-json-rpc" value="https://rpc.example">
    <input id="js-reown-project-id" value="project-id">
    <input id="js-coin-name" value="DOS">
  `
  document.title = 'DOS Chain'

  return require('../../../js/lib/smart_contract/connect')
}

describe('wallet connection', () => {
  beforeEach(() => {
    mockCreateAppKit.mockReset()
    mockWeb3.mockReset()
    delete window.ethereum
    window.web3 = null
  })

  test('initializes Reown AppKit for the configured custom chain', async () => {
    const appKit = {
      ready: jest.fn(() => Promise.resolve()),
      getIsConnectedState: jest.fn(() => false)
    }
    mockCreateAppKit.mockReturnValue(appKit)
    const { web3ModalInit } = loadConnect()

    await expect(web3ModalInit(jest.fn())).resolves.toBe(appKit)
    expect(mockCreateAppKit).toHaveBeenCalledWith(expect.objectContaining({
      projectId: 'project-id',
      networks: [expect.objectContaining({
        id: 43114,
        rpcUrls: { default: { http: ['https://rpc.example'] } }
      })]
    }))
    expect(appKit.ready).toHaveBeenCalled()
  })

  test('uses an injected EIP-1193 provider when AppKit is unavailable', async () => {
    const provider = {
      request: jest.fn(({ method }) => method === 'eth_requestAccounts' ? ['0x123'] : []),
      on: jest.fn()
    }
    window.ethereum = provider
    const { connectToProvider } = loadConnect()

    await expect(connectToProvider()).resolves.toBe(provider)
    expect(provider.request).toHaveBeenCalledWith({ method: 'eth_requestAccounts' })
    expect(mockWeb3).toHaveBeenCalledWith(provider)
  })

  test('restores a connected AppKit session after initialization', async () => {
    const provider = { on: jest.fn() }
    const appKit = {
      ready: jest.fn(() => Promise.resolve()),
      getIsConnectedState: jest.fn(() => true),
      getWalletProvider: jest.fn(() => provider)
    }
    mockCreateAppKit.mockReturnValue(appKit)
    const onReconnect = jest.fn()
    const { web3ModalInit } = loadConnect()

    await web3ModalInit(onReconnect, 'argument')

    expect(appKit.ready).toHaveBeenCalled()
    expect(onReconnect).toHaveBeenCalledWith('argument')
  })

  test('disconnects an active AppKit session through the public API', async () => {
    const appKit = {
      ready: jest.fn(() => Promise.resolve()),
      getIsConnectedState: jest.fn()
        .mockReturnValueOnce(false)
        .mockReturnValueOnce(true),
      disconnect: jest.fn(() => Promise.resolve())
    }
    mockCreateAppKit.mockReturnValue(appKit)
    const { disconnect, web3ModalInit } = loadConnect()
    await web3ModalInit(jest.fn())

    await disconnect()

    expect(appKit.disconnect).toHaveBeenCalledWith('eip155')
    expect(window.web3).toBeNull()
  })

  test('rejects when the AppKit modal closes without a provider', async () => {
    let stateHandler
    const appKit = {
      ready: jest.fn(() => Promise.resolve()),
      getIsConnectedState: jest.fn(() => false),
      getWalletProvider: jest.fn(() => null),
      subscribeProviders: jest.fn(() => jest.fn()),
      subscribeState: jest.fn(handler => {
        stateHandler = handler
        return jest.fn()
      }),
      open: jest.fn(() => Promise.resolve())
    }
    mockCreateAppKit.mockReturnValue(appKit)
    const { connectToProvider, web3ModalInit } = loadConnect()
    await web3ModalInit(jest.fn())

    const connection = connectToProvider()
    await Promise.resolve()
    stateHandler({ open: true })
    stateHandler({ open: false })

    await expect(connection).rejects.toThrow('Wallet connection was cancelled')
  })
})
