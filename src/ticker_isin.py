# Mapping des codes ticker Yuh → (ISIN, nom du titre)
# Source : factsheets dans investments-product-details/

TICKER_ISIN: dict[str, tuple[str, str]] = {
    'BTCW': ('GB00BJYDH287', 'WisdomTree Physical Bitcoin ETP'),
    'ETHW': ('GB00BJYDH394', 'WisdomTree Physical Ethereum ETP'),
    'ZGLD': ('CH0139101593', 'Swisscanto Gold ETF AA CHF DIS'),
    'IWDC': ('IE00B8BVCK12', 'iShares MSCI World CHF Hedged UCITS ETF Acc'),
    'XMME': ('IE00BTJRMP35', 'Xtrackers MSCI Emerging Markets UCITS ETF 1C'),
    'VUSD': ('IE00B3XXRP09', 'Vanguard S&P 500 UCITS ETF (USD) Dist'),
    'VWRD': ('IE00B3RBWM25', 'Vanguard FTSE All-World UCITS ETF (USD) Dist'),
    'MVSH': ('IE00BD1JRZ09', 'iShares MSCI World Min Vol Factor UCITS ETF'),
}

# Codes présents dans les CSV qui ne sont pas des titres financiers
NON_SECURITY_ASSETS: set[str] = {'SWQ', 'CHF', 'EUR', 'USD'}

# Mots-clés pour identifier un titre à partir du libellé de dividende
# (la colonne ASSET est vide sur les lignes CASH_TRANSACTION_RELATED_OTHER)
TICKER_NAME_KEYWORDS: dict[str, list[str]] = {
    'VUSD': ['S&P 500', 'Vanguard S&P'],
    'VWRD': ['All-World', 'FTSE All-World'],
    'IWDC': ['MSCI World CHF', 'iShares MSCI World', 'Developed World'],
    'XMME': ['Emerging Markets', 'Xtrackers'],
    'BTCW': ['Bitcoin'],
    'ETHW': ['Ethereum'],
    'ZGLD': ['Gold', 'Swisscanto'],
    'MVSH': ['Min Vol', 'Minimum Volatility'],
}
