import Web3 from 'web3'
import { createAppKit } from '@reown/appkit'
import { EthersAdapter } from '@reown/appkit-adapter-ethers'
import { compareChainIDs, formatError, showConnectElements, showConnectedToElements } from './common_helpers'
import { openWarningModal } from '../modals'

// @ts-ignore
const instanceChainIdStr = document.getElementById('js-chain-id').value
const instanceChainId = parseInt(instanceChainIdStr, 10)
// @ts-ignore
const jsonRPC = document.getElementById('js-json-rpc').value
// @ts-ignore
const reownProjectId = document.getElementById('js-reown-project-id').value

// Chosen wallet provider given by the dialog window
let provider

// Reown AppKit instance
let appKit
let appKitReady

const network = {
  id: instanceChainId,
  name: document.title,
  nativeCurrency: {
    decimals: 18,
    name: 'Native token',
    symbol: document.getElementById('js-coin-name').value
  },
  rpcUrls: {
    default: { http: [jsonRPC] }
  },
  blockExplorers: {
    default: { name: document.title, url: window.location.origin }
  }
}

/**
 * Setup the orchestra
 */
export async function web3ModalInit (connectToWallet, ...args) {
  if (!reownProjectId) {
    return null
  }

  appKit = createAppKit({
    adapters: [new EthersAdapter()],
    networks: [network],
    defaultNetwork: network,
    projectId: reownProjectId,
    metadata: {
      name: document.title,
      description: document.title,
      url: window.location.origin,
      icons: [`${window.location.origin}/favicon.ico`]
    },
    enableNetworkSwitch: false,
    features: {
      analytics: false,
      email: false,
      socials: [],
      swaps: false,
      onramp: false
    }
  })
  appKitReady = appKit.ready()
  await appKitReady

  if (appKit.getIsConnectedState()) {
    provider = appKit.getWalletProvider()
    if (provider) {
      await connectToWallet(...args)
    }
  }

  return appKit
}

const getInjectedProvider = async () => {
  if (!window.ethereum) {
    return null
  }

  try {
    const accounts = await window.ethereum.request({ method: 'eth_accounts' })
    return accounts.length > 0 ? window.ethereum : null
  } catch (_error) {
    return null
  }
}

const waitForAppKitProvider = () => {
  return new Promise((resolve, reject) => {
    let modalWasOpened = false
    let unsubscribeProviders = () => {}
    let unsubscribeState = () => {}
    const cleanup = () => {
      unsubscribeProviders()
      unsubscribeState()
    }

    unsubscribeProviders = appKit.subscribeProviders(providers => {
      if (providers.eip155) {
        cleanup()
        resolve(providers.eip155)
      }
    })
    unsubscribeState = appKit.subscribeState(({ open }) => {
      modalWasOpened = modalWasOpened || open
      if (modalWasOpened && !open && !appKit.getWalletProvider()) {
        cleanup()
        reject(new Error('Wallet connection was cancelled'))
      }
    })

    Promise.resolve(appKit.open({ view: 'Connect', namespace: 'eip155' })).catch(error => {
      cleanup()
      reject(error)
    })
  })
}

export const walletEnabled = async () => {
  provider = provider || (appKit && appKit.getWalletProvider()) || await getInjectedProvider()

  if (!provider) {
    return false
  }

  window.web3 = new Web3(provider)
  return true
}

export async function disconnect () {
  if (appKit && appKit.getIsConnectedState()) {
    await appKit.disconnect('eip155')
  } else if (provider && provider.disconnect) {
    await provider.disconnect()
  }

  provider = null

  window.web3 = null
}

/**
 * Disconnect wallet button pressed.
 */
export async function disconnectWallet () {
  await disconnect()

  showConnectElements()
}

export const connectToProvider = () => {
  return (async () => {
    if (appKit) {
      await appKitReady
      provider = appKit.getWalletProvider() || await waitForAppKitProvider()
    } else if (window.ethereum) {
      await window.ethereum.request({ method: 'eth_requestAccounts' })
      provider = window.ethereum
    } else {
      throw new Error('No wallet provider is available')
    }

    window.web3 = new Web3(provider)
    return provider
  })()
}

export const connectToWallet = async () => {
  await connectToProvider()

  // Subscribe to accounts change
  provider.on('accountsChanged', async (accs) => {
    const newAccount = accs && accs.length > 0 ? accs[0].toLowerCase() : null

    if (!newAccount) {
      await disconnectWallet()
    }

    fetchAccountData(showConnectedToElements, [])
  })

  // Subscribe to chainId change
  provider.on('chainChanged', (chainId) => {
    compareChainIDs(instanceChainId, chainId)
      .then(() => fetchAccountData(showConnectedToElements, []))
      .catch(error => {
        openWarningModal('Unauthorized', formatError(error))
      })
  })

  provider.on('disconnect', async () => {
    await disconnectWallet()
  })

  await fetchAccountData(showConnectedToElements, [])
}

export async function fetchAccountData (setAccount, args) {
  // Get a Web3 instance for the wallet
  if (provider) {
    window.web3 = new Web3(provider)
  }

  // Get list of accounts of the connected wallet
  const accounts = window.web3 && await window.web3.eth.getAccounts()

  // MetaMask does not give you all accounts, only the selected account
  if (accounts && accounts.length > 0) {
    const selectedAccount = accounts[0]

    setAccount(selectedAccount, ...args)
  }
}
