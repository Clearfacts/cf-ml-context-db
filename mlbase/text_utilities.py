import locale
import re
import calendar

from dateutil.relativedelta import relativedelta
from price_parser import Price
import dateparser
from datetime import datetime
import unidecode

def normalize_text(text):
    txt = unidecode.unidecode(text)
    txt = txt.lower()
    return txt

def extract_amount(s):
    amount = Price.fromstring(s).amount
    if amount is not None:
        return float(amount)
    else:
        return None


def get_datetime_patterns(p="%B", timeperiod="month"):
    """ Returns list of values for the given formattign pattern `p`

        Params:
            p: str. datetime formattting string
                (https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior)
            timeperiod: str.
                time period determines the number of periods and the delta to offset agains 1/1/2020
        Returns:
            list of str.
    """
    if timeperiod == "month":
        n_periods = 12
    else:
        raise RuntimeError(f"timeperiod {timeperiod} not implemented")
    start_date = datetime(2020, 1, 1)
    locales = ["nl_BE", "fr_BE"]
    strings = []
    for loc in locales:
        for i in range(n_periods):
            if timeperiod == "month":
                delta = relativedelta(months=i)
            d = start_date + delta
            locale.setlocale(locale.LC_TIME, loc)
            strings.append(d.strftime(p))
    return strings


d_day = r"(3[01]|[12][0-9]|0?[1-9])"
d_month = r"(1[012]|0?[1-9])"
d_year = r"((20)?([12][0-9]))"  # from 201x onwards
sep = r"[ \./-]+"

month_strings = get_datetime_patterns("%B")
month_strings.extend(get_datetime_patterns("%b"))
month_strings = [normalize_text(m) for m in month_strings]
# ocr errors
month_ocr_errors = {"ok>>": "okt"}
month_strings.extend(list(month_ocr_errors.keys()))
s_month = '(' + '|'.join(month_strings) + ')'

p_month = f"({d_month}|{s_month})"

date_patterns = [
    (d_day + sep + p_month + sep + d_year, False),
    (p_month + sep + d_day + sep + d_year, False),
    (d_day + sep + p_month, True),
    (d_month + sep + d_day, True)
]

period_map = {
    "dagen": 1,
    "tagen": 1,
    "dager": 1,
    "werkdagen": 1,
    "dag": 1,
    "day": 1,
    "days": 1,
    "jours": 1,
    "jour": 1,
    "week": 7,
    "weken": 7,
    "wochen": 7
}
period_exp = "(" + '|'.join([rf'\d+\s{p}' for p in period_map]) + ")"

relative_payment_periods = [
    rf'(betaald binnen (de )?{period_exp} na ontvangst)',
    rf'(be paid to within {period_exp})',
    rf'(be paid within {period_exp})',
    rf'(betalingen binnen (de )?{period_exp})',
    rf'(te betalen binnen (de )?{period_exp})',
    rf'(transfer \. within {period_exp})',
    rf'(betalingstermijn is {period_exp})',
    rf'(conditions de paiement \.*{period_exp})',
    rf'({period_exp} na factuurdatum over te (maken|schrijven))',
    rf'({period_exp} after invoice)',
    rf'(payment due {period_exp})',
    rf'({period_exp} from invoice date)',
    rf'({period_exp} ex End of month)',
    rf'({period_exp} einde maand)',
    rf'({period_exp} invoice date)',
    rf'({period_exp} na factuurdatum)',
    rf'({period_exp} factuurdatum)',
    rf'({period_exp} na datum)',
    rf'(binnen (de )?{period_exp})',
    rf'(na {period_exp})',
    rf'({period_exp} netto)',
    rf'(Netto {period_exp})',
    rf'(binnen (de )?{period_exp} over te (maken|schrijven))',
    rf'(Payable a {period_exp})',
    rf'(endeans les {period_exp})',
    rf'(innerhalb {period_exp})',
    rf'(termijnen.? {period_exp})',
]

end_of_month = [
    'einde maand',
    'eind volgende maand'
    'end of month',
    'end of next month',
    'fin du mois'
]

period_extraction = rf".*?(\d+)\s(dagen)|(\d+)\s(tagen)|(\d+)\s(week)|(\d+)\s(weken).*?"

immediate_payment_period = [
    r'betaling bij ontvangst factuur',
    r'payables (d.s|sur|a la) reception',
    r'betaling onmiddelijk (na|bij) ontvangst',
    r'contant betaalbaar',
    r'vooruitbetaling',
    r'paiement anticip.',
    r'contante betaling',
    r'contant betaald',
    r'debetkaart',
    r'immediately payable',
    r'(contant|onmiddellijk|per ommegaande) (te betalen|over te maken)',
    r'(betaalmethode|betalingsconditie)\s*:\s*(creditcard|paypal|mastercard|visa)',
    r'payment method (used)?\s*:\s*(creditcard|paypal|mastercard|visa)',
    r'(creditcard|paypal|mastercard|visa).? op',
    r'deze factuur is (reeds|al) (voldaan|betaald)',
    r'has been automatically settled',
    r'betaling (na|bij) ontvangst',
    r'payment upon receipt',
]


def get_separators(date_string):
    m = re.findall(sep, date_string)
    return m


def get_start_first_seperator(date_string):
    m = re.search(sep, date_string)
    if m:
        return m.start()
    else:
        return 0


def num_groups(regex):
    """ returns the number of groups defined in the regex string"""
    return re.compile(regex).groups


def parse_date(s):
    """ Parses the given string `s` and returns a Datetime object
        Returns:
            datetime.date or None if date could not be parsed
    """
    for error in month_ocr_errors:
        s = s.replace(error, month_ocr_errors[error])
    # rule for yyyy-mm-dd pattern  (dateparser always uses yyyy-dd-mm)
    re_yyyymmdd = r"(\d{4}).(\d{2}).(\d{2})"
    m = re.match(re_yyyymmdd, s)
    if m:
        year, month, day = m.groups()
        try:
            dt = datetime(int(year), int(month), int(day)).date()
            return dt
        except:
            pass

    d = dateparser.parse(s, languages=['nl', 'fr', 'de'])
    if not d:
        d = dateparser.parse(s, languages=['en'])
    if d:
        return d.date()
    else:
        # print(f"WARNING: couldn't parse date '{s}'")
        return None


def find_dates(s, expected_year):
    """ returns list of dates found in the text

        Params:
            s: str. input text to search
            expected_year: int. year to use if date pattern are missing year. e.g. 1/1 => f"1/1/{expected_year}"
        Returns:
            list of tuples. (str:matched string, datetime)
    """
    s = normalize_text(s)
    res = []
    for p, add_year in date_patterns:
        while True:
            m = re.search(p, s)
            if m:
                date_string = m[0]
                if add_year:
                    sep = get_separators(date_string)
                    if len(sep) > 0:
                        sep = sep[0]
                    else:
                        sep = ' '
                    date_string += f"{sep}{expected_year}"

                if len(set(get_separators(date_string))) > 1:
                    # ignore date constructs with different seperators
                    # so remove beginning of found pattern
                    s = s[m.start() + get_start_first_seperator(date_string) + 1:]
                else:
                    # remove match to avoid duplicates
                    s = s[:m.start()] + " " + s[m.end():]
                    # add date string to result set
                    res.append((date_string, parse_date(date_string)))
            else:
                break
        if len(s) == 0:
            return res
    return res


def is_complete_date(s):
    s = normalize_text(s)
    for p, add_year in date_patterns:
        m = re.match(p, s)
        if m is not None:
            return True, add_year
    return False, False


# returns: (is_date, missing_year)
assert (is_complete_date("januari") == (False, False))
assert (is_complete_date("11/12") == (True, True))
assert (is_complete_date("11/12/20") == (True, False))
assert (is_complete_date("10 januari") == (True, True))
assert (is_complete_date("10 april 2020") == (True, False))
assert (is_complete_date("10 10 2020") == (True, False))


def is_year(s):
    m = re.match(d_year, s)
    return m is not None


def get_last_date_of_month(ref_date):
    _, last_day = calendar.monthrange(ref_date.year, ref_date.month)
    last_day_of_month = datetime(ref_date.year, ref_date.month, last_day).date()
    return last_day_of_month


def extract_period_in_days(period_string):
    period_string = normalize_text(period_string)
    m = re.match(period_extraction, period_string)
    n_days = None
    if m:
        n = int(m[1])
        for i in range(2, num_groups(period_extraction)):
            if m[i] is not None:
                n_days = n * period_map[m[i]]
                break
    return n_days


def reference_end_of_month(period_string):
    for pattern in end_of_month:
        m = re.search(pattern, period_string)
        if m is not None:
            return True
    return False


def find_relative_payment_periods(s):
    """ uses the patterns in `relative_payment_periods` to find relative payment periods

        Params:
            s: str. input text to search
        Returns:
            list of tuples. (str:matched string, int:number of days of relative period)
    """
    s = normalize_text(s)
    res = []
    for p in relative_payment_periods:
        # find matching rule
        while True:
            m = re.search(p, s)
            if m:
                # remove match to avoid duplicates
                s = s[:m.start()] + " " + s[m.end():]
                # extract value and period from period string
                period_string = m[0]
                m = re.match(period_extraction, period_string)
                if m:
                    n = int(m[1])
                    n_days = None
                    for i in range(2, num_groups(period_extraction)):
                        if m[i] is not None:
                            n_days = n * period_map[m[i]]
                            break
                    res.append((period_string, n_days))
            else:
                break
        if len(s) == 0:
            return res
    return res


def find_immediate_payment_periods(s):
    """ uses the patterns in `immediate_payment_period` to find immediate payment periods

        Params:
            s: str. input text to search
        Returns:
            list of tuples. (str:matched string, int: 0)
    """
    s = normalize_text(s)
    res = []
    for p in immediate_payment_period:
        while True:
            # find matching rule
            m = re.search(p, s)
            if m:
                period_string = m[0]
                res.append((period_string, 0))
                # remove match to avoid duplicates
                s = s[:m.start()] + " " + s[m.end():]
            else:
                break
        if len(s) == 0:
            return res

    return res
