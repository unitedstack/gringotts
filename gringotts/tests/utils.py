import datetime

def remove_microsecond(adatetime):
    adatetime = datetime.datetime(year=adatetime.year,
                                  month=adatetime.month,
                                  day=adatetime.day,
                                  hour=adatetime.hour,
                                  minute=adatetime.minute,
                                  second=adatetime.second)
    return adatetime
