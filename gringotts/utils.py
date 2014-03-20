#!/usr/bin/python
# -*- coding: utf-8 -*-
from decimal import Decimal, ROUND_HALF_UP
import calendar


def _quantize_decimal(value):
    if isinstance(value, Decimal):
       return  value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def next_month_days(year, month):
    year += month / 12
    month = month % 12 + 1
    return calendar.monthrange(year, month)[1]
