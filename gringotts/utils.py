#!/usr/bin/python
# -*- coding: utf-8 -*-
from decimal import Decimal, ROUND_HALF_UP


def _quantize_decimal(value):
    if isinstance(value, Decimal):
       return  value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
