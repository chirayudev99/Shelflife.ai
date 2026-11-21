"""Canonical company metadata used by search and conversation context."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CompanyId = Literal["ETERNAL", "SWIGGY", "ZEPTO"]


@dataclass(frozen=True, slots=True)
class Company:
    ticker: CompanyId
    display_name: str
    search_aliases: tuple[str, ...]
    domain_hints: tuple[str, ...]

    @property
    def search_context(self) -> str:
        return " ".join(self.domain_hints)


@dataclass(frozen=True, slots=True)
class CompanyRegistry:
    companies: tuple[Company, ...]

    def get(self, ticker: str) -> Company:
        for company in self.companies:
            if company.ticker == ticker:
                return company
        raise KeyError(f"Unknown company ticker: {ticker}")

    def detect(self, text: str) -> list[CompanyId]:
        lowered = text.casefold()
        mentions: list[tuple[int, CompanyId]] = []
        for company in self.companies:
            positions = [
                match.start()
                for alias in company.search_aliases
                if (
                    match := re.search(
                        rf"\b{re.escape(alias)}\b",
                        lowered,
                    )
                )
            ]
            if positions:
                mentions.append((min(positions), company.ticker))
        return [ticker for _, ticker in sorted(mentions)]


COMPANY_REGISTRY = CompanyRegistry(
    companies=(
        Company(
            ticker="ETERNAL",
            display_name="Eternal (Blinkit)",
            search_aliases=("blinkit", "zomato", "eternal"),
            domain_hints=("Eternal", "Blinkit", "quick commerce"),
        ),
        Company(
            ticker="SWIGGY",
            display_name="Swiggy (Instamart)",
            search_aliases=("swiggy", "instamart"),
            domain_hints=("Swiggy", "Instamart", "quick commerce"),
        ),
        Company(
            ticker="ZEPTO",
            display_name="Zepto",
            search_aliases=("zepto", "kiranakart"),
            domain_hints=("Zepto", "Kiranakart", "UDRHP"),
        ),
    )
)
