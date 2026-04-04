import re

# Known junk numbers that appear in Google search results
# (mathematical fractions rendered as numbers, star ratings, etc.)
KNOWN_JUNK = {
    "0892857143", "0071428571", "0178571429", "0142857143",
    "0000042915344", "00056354413", "0357142857", "0535714286",
    "0714285714", "0464285714", "0321428571", "0250000000",
}

# Valid Indian landline STD codes (major cities)
VALID_STD_CODES = {
    "011", "022", "033", "040", "044", "080",  # metros
    "020", "079", "0120", "0124", "0172", "0141",  # tier 1
    "0135", "0161", "0175", "0177", "0181", "0183",  # tier 2
    "0191", "0194", "0212", "0217", "0231", "0233",
    "0240", "0241", "0250", "0251", "0253", "0257",
    "0261", "0265", "0268", "0278", "0281", "0285",
    "0291", "0294", "0326", "0341", "0343", "0353",
    "0361", "0364", "0381", "0385", "0389", "0413",
    "0416", "0422", "0424", "0431", "0435", "0452",
    "0461", "0471", "0474", "0477", "0484", "0487",
    "0495", "0497", "0512", "0522", "0532", "0542",
    "0551", "0562", "0571", "0581", "0591", "0612",
    "0621", "0631", "0641", "0651", "0657", "0661",
    "0671", "0674", "0712", "0721", "0731", "0744",
    "0751", "0755", "0761", "0771", "0788", "0816",
    "0821", "0824", "0831", "0836", "0866", "0870",
    "0877", "0884", "0891",
}


def is_valid_indian_phone(phone: str) -> bool:
    """Validate that a phone number is a real Indian phone number.

    Accepts:
    - Indian mobile: +91 XXXXXXXXXX or [6-9]XXXXXXXXXX (10 digits)
    - Indian landline: 0XX-XXXXXXXX (STD code + number)
    - Toll-free: 1800-XXX-XXXX
    - International: +XX with valid country code
    """
    cleaned = re.sub(r"[\s\-\(\).]", "", phone)
    digits = re.sub(r"\D", "", cleaned)

    # Reject known junk
    if digits in KNOWN_JUNK or cleaned in KNOWN_JUNK:
        return False

    # Reject if too many leading zeros (Google artifacts)
    if digits.startswith("000"):
        return False

    # Reject if digit distribution looks non-phone
    if len(set(digits)) <= 3:
        return False

    # === +91 prefix: could be mobile or landline ===
    if digits.startswith("91") and 12 <= len(digits) <= 14:
        rest = digits[2:]
        # Mobile: 10 digits starting 6-9
        if len(rest) == 10 and rest[0] in "6789":
            return True
        # Landline: area code (without leading 0) + number
        # e.g. +91 22 3008 9444 → digits=912230089444, rest=2230089444
        for code_len in (2, 3):
            area = "0" + rest[:code_len]
            if area in VALID_STD_CODES:
                remaining = rest[code_len:]
                if 6 <= len(remaining) <= 8:
                    return True
        return False

    # === Indian mobile without country code: 10 digits starting 6-9 ===
    if len(digits) == 10 and digits[0] in "6789":
        return True

    # === Toll-free: 1800 ===
    if digits.startswith("1800") and 11 <= len(digits) <= 13:
        return True

    # === Indian landline: starts with 0 + valid STD code ===
    if digits.startswith("0") and 10 <= len(digits) <= 12:
        # Check STD code (3 or 4 digits including the leading 0)
        for code_len in (3, 4):
            code = digits[:code_len]
            if code in VALID_STD_CODES:
                remaining = digits[code_len:]
                # Landline numbers are 6-8 digits after STD code
                if 6 <= len(remaining) <= 8:
                    return True

    # === International with + prefix ===
    if cleaned.startswith("+") and len(digits) >= 10:
        # Common valid country codes
        if digits[:2] in ("44", "1", "61", "65", "60", "86", "81", "49", "33", "971"):
            return True
        if digits.startswith("91"):
            return is_valid_indian_phone(f"+91{digits[2:]}")

    return False


def clean_phone(phone: str) -> str:
    """Normalize phone number format."""
    cleaned = phone.strip()
    # Remove multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned
