from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4


class SportType(Enum):
    SOCCER = auto()
    BASKETBALL = auto()
    TENNIS = auto()
    RUGBY = auto()
    AFL = auto()
    NRL = auto()
    CRICKET = auto()
    HORSE_RACING = auto()
    ESPORTS = auto()
    OTHER = auto()


class MarketType(Enum):
    WIN = auto()  # Home/Away or 1X2
    HANDICAP = auto()
    TOTAL_OVER_UNDER = auto()
    MONEYLINE = auto()
    CORRECT_SCORE = auto()
    PLAYER_PROPS = auto()
    OTHER = auto()


class OddsFormat(Enum):
    DECIMAL = auto()  # 2.0, 1.5, etc.
    FRACTIONAL = auto()  # 1/1, 1/2, etc.
    AMERICAN = auto()  # +100, -150, etc.


@dataclass
class Bookmaker:
    id: str
    name: str
    base_url: str
    logo_url: Optional[str] = None
    commission: float = 0.0  # Some bookmakers might have a commission
    min_stake: float = 0.0  # Minimum stake allowed
    max_stake: Optional[float] = None  # Maximum stake allowed, None if no limit


@dataclass
class Outcome:
    name: str  # Name of the selection (e.g., "Manchester United", "Draw", "Over 2.5")
    odds: float  # Decimal odds


@dataclass
class Market:
    id: str
    type: MarketType
    name: str  # Human-readable market name (e.g., "Match Winner", "Over/Under 2.5 Goals")
    outcomes: List[Outcome]
    is_live: bool = False


@dataclass
class Event:
    id: str
    sport: SportType
    home_team: str
    away_team: str
    competition: str  # League or tournament name
    start_time: datetime
    markets: List[Market]
    bookmaker: Bookmaker
    url: str  # URL to the event page
    created_at: datetime = datetime.now()
    
    def get_market_by_type(self, market_type: MarketType) -> Optional[Market]:
        """Get a market by its type"""
        for market in self.markets:
            if market.type == market_type:
                return market
        return None


@dataclass
class ArbitrageOpportunity:
    event_description: str  # Combined event description (e.g. "Manchester United vs Liverpool")
    market_description: str  # Description of the market (e.g. "Match Winner")
    selections: List[Tuple[str, float, Bookmaker]]  # List of (selection name, odds, bookmaker)
    profit_percentage: float  # Arbitrage profit % (e.g., 2.5)
    required_investment: float  # Total stake required
    stakes: Dict[str, float]  # Stake for each selection
    id: UUID = uuid4()
    detection_time: datetime = datetime.now()
    
    @property
    def is_profitable(self) -> bool:
        """Check if the arbitrage opportunity is profitable"""
        return self.profit_percentage > 0
    
    def get_stake_for_selection(self, selection_name: str) -> float:
        """Get the stake amount for a specific selection"""
        return self.stakes.get(selection_name, 0.0)
    
    def get_expected_return(self) -> float:
        """Calculate the expected return from the arbitrage opportunity"""
        return self.required_investment * (1 + self.profit_percentage / 100)


@dataclass
class ScrapingResult:
    bookmaker: Bookmaker
    events: List[Event]
    timestamp: datetime = datetime.now()
    success: bool = True
    error_message: Optional[str] = None
