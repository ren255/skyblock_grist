"""Guards against swapping the Bazaar order books.

The API's `buy_summary` / `sell_summary` naming is counter-intuitive, and mixing
them up would corrupt every profit column while still producing plausible
numbers. The fixtures below are real FLAWED/FLAWLESS_SAPPHIRE_GEM values.
"""

import pytest

from app.api.models import BazaarProduct
from app.api.pricing import compute_gem_prices

# Real values observed on the live Bazaar.
FLAWED_BEST_BUY_ORDER = 376.6  # sell_summary[0] — what a buy order costs
FLAWED_BEST_SELL_OFFER = 876.9  # buy_summary[0] — what buying now costs
FLAWED_WEIGHTED_BUY_PRICE = 1169.7  # quick_status.buyPrice — must not be used

FLAWLESS_BEST_BUY_ORDER = 2513194.6  # sell_summary[0] — instant sell price
FLAWLESS_BEST_SELL_OFFER = 2624834.2  # buy_summary[0] — sell order price
FLAWLESS_BUY_MOVING_WEEK = 15613.0


def _product(sell_top: float, buy_top: float, buy_moving_week: float = 0.0):
    """Build a product. `sell_top` is the best buy order, `buy_top` the best offer."""
    return BazaarProduct.model_validate(
        {
            "sell_summary": [{"pricePerUnit": sell_top}],
            "buy_summary": [{"pricePerUnit": buy_top}],
            "quick_status": {"buyMovingWeek": buy_moving_week},
        }
    )


def _flawed() -> BazaarProduct:
    return _product(FLAWED_BEST_BUY_ORDER, FLAWED_BEST_SELL_OFFER)


def _flawless() -> BazaarProduct:
    return _product(
        FLAWLESS_BEST_BUY_ORDER, FLAWLESS_BEST_SELL_OFFER, FLAWLESS_BUY_MOVING_WEEK
    )


def test_prices_are_taken_from_top_of_book():
    prices = compute_gem_prices(_flawed(), _flawless())

    assert prices.buy_order == FLAWED_BEST_BUY_ORDER
    assert prices.sell_order == round(FLAWLESS_BEST_SELL_OFFER, 2)
    assert prices.insta_sell == round(FLAWLESS_BEST_BUY_ORDER, 2)

    # The two values a swap or a quick_status mix-up would produce instead.
    assert prices.buy_order != FLAWED_BEST_SELL_OFFER
    assert prices.buy_order != FLAWED_WEIGHTED_BUY_PRICE


def test_avg_selling_per_minute_derived_from_flawless_buy_moving_week():
    prices = compute_gem_prices(_flawed(), _flawless())

    # 15613 units a week over 7*24*60 minutes.
    assert prices.avg_selling_per_minute == pytest.approx(1.5489, abs=1e-4)


def test_order_book_is_not_crossed():
    """Pins the fixtures to a real market invariant: books are never crossed.

    The invariant itself was checked against all 2124 products of a live
    response (zero violations); this test fixes it for the fixtures so they stay
    representative. `test_swapped_summaries_break_the_spread_invariant` is what
    proves a swap would actually be caught.
    """
    for product in (_flawed(), _flawless()):
        assert product.sell_summary[0].pricePerUnit <= product.buy_summary[0].pricePerUnit


def test_insta_sell_does_not_exceed_sell_order():
    prices = compute_gem_prices(_flawed(), _flawless())

    assert prices.insta_sell <= prices.sell_order


def test_swapped_summaries_break_the_spread_invariant():
    """Proves the invariant above actually detects a swap."""
    swapped_flawless = _product(
        FLAWLESS_BEST_SELL_OFFER, FLAWLESS_BEST_BUY_ORDER, FLAWLESS_BUY_MOVING_WEEK
    )

    prices = compute_gem_prices(_flawed(), swapped_flawless)

    assert prices.insta_sell > prices.sell_order


@pytest.mark.parametrize(
    "flawed_sell, flawless_buy, flawless_sell",
    [
        ([], [{"pricePerUnit": 1.0}], [{"pricePerUnit": 1.0}]),
        ([{"pricePerUnit": 1.0}], [], [{"pricePerUnit": 1.0}]),
        ([{"pricePerUnit": 1.0}], [{"pricePerUnit": 1.0}], []),
    ],
)
def test_returns_none_when_order_book_empty(flawed_sell, flawless_buy, flawless_sell):
    flawed = BazaarProduct.model_validate(
        {
            "sell_summary": flawed_sell,
            "buy_summary": [{"pricePerUnit": 1.0}],
            "quick_status": {"buyMovingWeek": 0.0},
        }
    )
    flawless = BazaarProduct.model_validate(
        {
            "sell_summary": flawless_sell,
            "buy_summary": flawless_buy,
            "quick_status": {"buyMovingWeek": 0.0},
        }
    )

    assert compute_gem_prices(flawed, flawless) is None


def test_values_are_rounded():
    flawed = _product(1.23456, 9.0)
    flawless = _product(2.98765, 3.14159, 1.0)

    prices = compute_gem_prices(flawed, flawless)

    assert prices.buy_order == 1.23
    assert prices.insta_sell == 2.99
    assert prices.sell_order == 3.14
    assert prices.avg_selling_per_minute == 0.0001
