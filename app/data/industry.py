"""Collapse Wikipedia's ~40 granular sector labels into the 11 ICB industries.

Why: the FTSE 100 spread over 40 sectors leaves many singletons ("Chemicals",
"Leisure Goods"). A cross-sectional regression on singleton dummies is
rank-deficient and the "factor return" is just that one stock's return. The ICB
industry level gives groups big enough to estimate something meaningful.
"""
from __future__ import annotations

ICB_INDUSTRIES = [
    "Basic Materials", "Consumer Discretionary", "Consumer Staples", "Energy",
    "Financials", "Health Care", "Industrials", "Real Estate",
    "Technology", "Telecommunications", "Utilities",
]

_EXPLICIT = {
    "Financial Services": "Financials", "Banks": "Financials",
    "Banking Services": "Financials", "Insurance": "Financials",
    "Life Insurance": "Financials", "Non-Life Insurance": "Financials",
    "Investment Trusts": "Financials", "Collective Investments": "Financials",
    "Real Estate Investment Trusts": "Real Estate", "Real Estate": "Real Estate",
    "Mining": "Basic Materials", "Chemicals": "Basic Materials",
    "Oil & Gas Producers": "Energy",
    "Multiline Utilities": "Utilities",
    "Electrical Utilities & Independent Power Producers": "Utilities",
    "Pharmaceuticals & Biotechnology": "Health Care",
    "Health Care Equipment & Supplies": "Health Care",
    "Software & Computer Services": "Technology",
    "Electronic Equipment & Parts": "Technology",
    "Telecommunications Services": "Telecommunications",
    "Mobile Telecommunications": "Telecommunications",
    "Beverages": "Consumer Staples", "Tobacco": "Consumer Staples",
    "Food & Tobacco": "Consumer Staples", "Food & Drug Retailing": "Consumer Staples",
    "Media": "Consumer Discretionary", "Travel & Leisure": "Consumer Discretionary",
    "General Retailers": "Consumer Discretionary", "Retailers": "Consumer Discretionary",
    "Retail Hospitality": "Consumer Discretionary",
    "Leisure Goods": "Consumer Discretionary", "Personal Goods": "Consumer Discretionary",
    "Household Goods & Home Construction": "Consumer Discretionary",
    "Aerospace & Defence": "Industrials", "Support Services": "Industrials",
    "Industrial Support Services": "Industrials", "General Industrials": "Industrials",
    "Industrial Engineering": "Industrials", "Industrial Goods And Services": "Industrials",
    "Homebuilding & Construction Supplies": "Industrials",
}

# Fallback keyword rules, applied in order, for labels Wikipedia adds later.
_KEYWORDS = [
    ("bank", "Financials"), ("insur", "Financials"), ("financ", "Financials"),
    ("invest", "Financials"), ("real estate", "Real Estate"),
    ("mining", "Basic Materials"), ("chemical", "Basic Materials"),
    ("oil", "Energy"), ("gas", "Energy"), ("utilit", "Utilities"),
    ("pharma", "Health Care"), ("health", "Health Care"),
    ("software", "Technology"), ("technolog", "Technology"),
    ("telecom", "Telecommunications"),
    ("beverage", "Consumer Staples"), ("tobacco", "Consumer Staples"),
    ("food", "Consumer Staples"), ("retail", "Consumer Discretionary"),
    ("media", "Consumer Discretionary"), ("leisure", "Consumer Discretionary"),
    ("travel", "Consumer Discretionary"), ("goods", "Consumer Discretionary"),
    ("industrial", "Industrials"), ("aerospace", "Industrials"),
    ("engineer", "Industrials"), ("construction", "Industrials"),
    ("support", "Industrials"),
]


def to_industry(sector: str) -> str:
    if not sector:
        return "Industrials"
    s = str(sector).strip()
    if s in _EXPLICIT:
        return _EXPLICIT[s]
    low = s.lower()
    for kw, ind in _KEYWORDS:
        if kw in low:
            return ind
    return "Industrials"
