"""Plain-English one-liners for FTSE 100 companies.

Why hand-written rather than pulled from a feed: the provider's business
summary reads like a filing ("Kingfisher plc, together with its subsidiaries,
supplies home improvement products and services through a network of retail
stores..."), which is precisely the jargon we are trying to spare a new joiner
on their first screen. "Owns B&Q and Screwfix" tells them more in five words.

Index constituents change a few times a year, so anything not listed here falls
back to the company's name and ICB industry via `describe()`. That degrades
quietly rather than showing a blank or a wrong guess.
"""
from __future__ import annotations

# Keyed on the Yahoo symbol, which is what the rest of the app passes around.
DESCRIPTIONS: dict[str, str] = {
    # --- Basic Materials ---
    "AAL.L": "Global miner - copper, iron ore, platinum and diamonds (De Beers).",
    "ANTO.L": "Chilean copper miner, controlled by the Luksic family.",
    "CRDA.L": "Speciality chemicals for cosmetics, crop care and pharmaceuticals.",
    "RIO.L": "One of the world's largest miners - iron ore, aluminium, copper.",
    "FRES.L": "Mexican silver and gold miner, the largest primary silver producer.",
    "GLEN.L": "Miner and commodity trader - one of the biggest trading houses on earth.",
    "MNDI.L": "Paper and packaging, from corrugated boxes to industrial bags.",
    "EDV.L": "Gold miner operating across West Africa.",

    # --- Energy & Utilities ---
    "BP.L": "Oil and gas major, increasingly in wind and solar.",
    "SHEL.L": "Oil and gas major and the largest company in the index.",
    "CNA.L": "Owns British Gas - energy supply, plus storage and generation.",
    "NG.L": "Owns and runs the electricity transmission network in England and Wales.",
    "SSE.L": "Scottish utility focused on renewables and electricity networks.",
    "SVT.L": "Water and waste water for the Midlands.",
    "UU.L": "Water and waste water for the north west of England.",

    # --- Financials: banks ---
    "BARC.L": "UK high-street bank with a large investment bank attached.",
    "HSBA.L": "Global bank, most of its profit from Asia despite the London listing.",
    "LLOY.L": "The UK's biggest mortgage lender - Lloyds, Halifax, Bank of Scotland.",
    "NWG.L": "NatWest and RBS. Was 84% state-owned after the 2008 bailout.",
    "STAN.L": "Emerging-markets bank - Asia, Africa and the Middle East.",
    "INVP.L": "Anglo-South African specialist bank and wealth manager.",
    "BGEO.L": "The largest bank in Georgia, listed in London.",

    # --- Financials: insurance ---
    "ADM.L": "Car insurance - Admiral, Elephant, Confused.com.",
    "AV.L": "Insurance, pensions and savings, mostly in the UK.",
    "BEZ.L": "Lloyd's of London specialist insurer - cyber, marine, political risk.",
    "HSX.L": "Bermuda-based specialty insurer and reinsurer.",
    "LGEN.L": "Pensions and annuities, and one of Europe's largest asset managers.",
    "PRU.L": "Life insurance and savings across Asia and Africa.",
    "PHNX.L": "Consolidator of closed life and pension books - Standard Life brand.",

    # --- Financials: asset management & markets ---
    "ALW.L": "Global equity investment trust, formed from Alliance Trust and Witan.",
    "FCIT.L": "The world's oldest collective investment fund, launched in 1868.",
    "ICG.L": "Private markets manager - private debt, credit and equity.",
    "IGG.L": "Online trading platform for spread bets and CFDs.",
    "III.L": "Private equity and infrastructure. Its big win is discount retailer Action.",
    "LSEG.L": "Runs the London Stock Exchange, but mostly a data business now (Refinitiv).",
    "SDR.L": "Asset manager, still substantially family-controlled.",
    "SMT.L": "Baillie Gifford's global growth trust - big early bets on Tesla and Amazon.",
    "STJ.L": "Wealth manager working through a network of self-employed advisers.",
    "ABDN.L": "Asset manager, owner of the Interactive Investor platform.",
    "PSH.L": "Bill Ackman's Pershing Square, listed as a closed-end fund.",

    # --- Real Estate ---
    "BLND.L": "REIT - London offices and retail parks.",
    "LAND.L": "REIT - central London offices and major shopping centres.",
    "SGRO.L": "REIT - warehouses and logistics sheds, the Amazon-era landlord.",
    "LMP.L": "REIT focused on logistics and convenience property.",
    "UTG.L": "Purpose-built student accommodation across UK university cities.",

    # --- Health Care ---
    "AZN.L": "Pharmaceuticals - oncology, respiratory, and the Oxford Covid vaccine.",
    "GSK.L": "Pharmaceuticals and vaccines. Spun out Haleon in 2022.",
    "SN.L": "Medical devices - hip and knee implants, wound care.",
    "CTEC.L": "Medical devices for ostomy, continence and advanced wound care.",
    "HIK.L": "Generic and branded generic medicines, strong in the Middle East.",

    # --- Consumer Staples ---
    "ABF.L": "An odd pairing: Primark, plus sugar, yeast and grocery brands.",
    "BATS.L": "Tobacco - Dunhill, Lucky Strike, and vaping brand Vuse.",
    "DGE.L": "Spirits and beer - Guinness, Johnnie Walker, Smirnoff, Tanqueray.",
    "IMB.L": "Tobacco - Davidoff, Winston, Rizla.",
    "MKS.L": "Marks & Spencer - food halls, clothing and homeware.",
    "SBRY.L": "The UK's second-largest supermarket, and owner of Argos.",
    "TSCO.L": "The UK's largest supermarket, around a quarter of the grocery market.",
    "CCH.L": "Bottles and sells Coca-Cola across 29 countries.",

    # --- Consumer Discretionary ---
    "BRBY.L": "Luxury fashion, best known for the trench coat and the check.",
    "BTRW.L": "Housebuilder, formed by the merger of Barratt and Redrow.",
    "ENT.L": "Betting and gaming - Ladbrokes, Coral, bwin.",
    "GAW.L": "Games Workshop - Warhammer miniatures, and fiercely profitable.",
    "IAG.L": "Owns British Airways, Iberia, Aer Lingus and Vueling.",
    "IHG.L": "Hotel brands - Holiday Inn, Crowne Plaza, InterContinental.",
    "INF.L": "B2B exhibitions and academic publishing (Taylor & Francis).",
    "JD.L": "Sportswear and trainers retail across the UK and Europe.",
    "KGF.L": "Home improvement retail - owns B&Q and Screwfix in the UK, "
             "plus Castorama and Brico Depot in France.",
    "NXT.L": "Clothing and homeware retailer, widely admired for its capital discipline.",
    "PSN.L": "Volume housebuilder, historically the highest-margin of the UK builders.",
    "PSON.L": "Education - textbooks, online learning and professional testing.",
    "REL.L": "Scientific publishing (Elsevier) and legal and risk data (LexisNexis).",
    "RKT.L": "Household and health brands - Dettol, Durex, Nurofen, Finish.",
    "ULVR.L": "Consumer goods - Dove, Hellmann's, Magnum, Domestos.",
    "WTB.L": "Owns Premier Inn, the UK's largest hotel chain.",
    "AUTO.L": "Auto Trader - the dominant UK marketplace for used cars.",
    "RMV.L": "Rightmove - the dominant UK property portal.",
    "WPP.L": "Advertising and media buying holding company.",
    "TW.L": "Taylor Wimpey - volume housebuilder.",
    "BKG.L": "Berkeley Group - housebuilder focused on London and the South East.",
    "VTY.L": "Vistry - housebuilder, now focused on partnership and affordable housing.",

    # --- Industrials ---
    "BA.L": "Defence - submarines, Typhoon jets, and a large US business.",
    "BAB.L": "Defence engineering and support, including nuclear submarine work.",
    "BNZL.L": "Unglamorous but relentless: distributes the packaging, gloves and "
              "cleaning supplies that other businesses get through.",
    "CPG.L": "Contract catering - staff canteens, hospitals, stadiums, schools.",
    "DCC.L": "Sales and distribution group, mostly LPG and heating oil.",
    "DPLM.L": "Distributes technical bits and pieces - seals, wiring, lab supplies.",
    "HWDN.L": "Supplies fitted kitchens to the building trade, never to the public.",
    "IMI.L": "Engineering for fluid and motion control - valves and actuators.",
    "ITRK.L": "Testing, inspection and certification - checks that things are what "
              "they claim to be.",
    "MRO.L": "Melrose - buys underperforming manufacturers, fixes them, sells them. "
             "Now mostly GKN Aerospace.",
    "RR.L": "Rolls-Royce - aero engines, and paid per hour that those engines fly.",
    "RTO.L": "Pest control and hygiene - Rentokil and Initial.",
    "SMIN.L": "Diversified engineering - airport scanners, seals, medical devices.",
    "SPX.L": "Steam systems and precision pumps. Sells into almost every industry.",
    "WEIR.L": "Pumps and crushers for mining. Its fortunes track the miners'.",
    "AHT.L": "Ashtead - construction equipment rental, mostly in the US as Sunbelt.",
    "MTLN.L": "Metlen - Greek metals and energy group, dual-listed in London.",

    # --- Technology & Telecoms ---
    "CCC.L": "Computacenter - supplies and manages IT kit for large organisations.",
    "HLMA.L": "Halma - buys and holds niche safety and environmental technology firms.",
    "SGE.L": "Sage - accounting and payroll software for small businesses.",
    "BT-A.L": "BT - broadband and mobile (EE), and owns the Openreach network.",
    "VOD.L": "Vodafone - mobile networks across Europe and Africa.",
    "EXPN.L": "Experian - credit bureau and the data behind credit scores.",
    "SPT.L": "Spirent - test and measurement kit for networks.",
    "WISE.L": "Wise - low-cost international money transfers.",
    "AAF.L": "Airtel Africa - mobile networks and mobile money across 14 countries.",
    "PCT.L": "Polar Capital Technology Trust - a listed fund holding global tech stocks.",

    # --- names outside the core/long windows, described so a constituent
    # --- change does not leave a gap on the front page
    "CCEP.L": "Bottles and sells Coca-Cola across western Europe and Australia.",
    "HLN.L": "Haleon - consumer health spun out of GSK. Sensodyne, Panadol, Centrum.",
    "MNG.L": "M&G - savings and asset management, demerged from Prudential in 2019.",
    "SDLF.L": "Life insurance and pensions under the Standard Life name, which now "
              "sits within Phoenix Group.",
    "BBOX.L": "Tritax Big Box - REIT owning the very large distribution warehouses.",
}

# Sector labels are ICB industries, which are accurate but terse. A friendlier
# gloss for the tooltip.
INDUSTRY_GLOSS: dict[str, str] = {
    "Basic Materials": "Miners and chemicals",
    "Consumer Discretionary": "Things people buy when they feel well off",
    "Consumer Staples": "Things people buy regardless",
    "Energy": "Oil and gas",
    "Financials": "Banks, insurers and asset managers",
    "Health Care": "Pharmaceuticals and medical devices",
    "Industrials": "Manufacturing, engineering and business services",
    "Real Estate": "Property owners and developers",
    "Technology": "Software and hardware",
    "Telecommunications": "Phone and broadband networks",
    "Utilities": "Water, power and networks",
}


def describe(ticker: str, name: str = "", industry: str = "") -> str:
    """A one-line description, or a graceful fallback for an unlisted name."""
    hit = DESCRIPTIONS.get(str(ticker).strip().upper())
    if hit:
        return hit
    if name and industry:
        return f"{name} - a {industry.lower()} company. (No description written yet.)"
    return name or str(ticker)


def gloss(industry: str) -> str:
    return INDUSTRY_GLOSS.get(str(industry), "")


def coverage(tickers) -> dict:
    """How much of a universe we have written up. Used by the smoke test so a
    constituent change surfaces as a nudge rather than a silent gap."""
    known = [t for t in tickers if str(t).strip().upper() in DESCRIPTIONS]
    missing = [t for t in tickers if str(t).strip().upper() not in DESCRIPTIONS]
    return {"known": len(known), "missing": missing,
            "pct": round(100 * len(known) / max(len(list(tickers)), 1), 1)}
