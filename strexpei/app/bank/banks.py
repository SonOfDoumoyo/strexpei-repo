
async def bank_n_codes(user_bank_name):
    banks = {
        "044":"Access Bank Nigeria Plc",
        "050":"Ecobank Nigeria",
        "084":"Enterprise Bank Plc",
        "070":"Fidelity Bank Plc",
        "011":"First Bank of Nigeria Plc",
        "214":"First City Monument Bank",
        "058":"Guaranty Trust Bank Plc",
        "301":"Jaiz Bank",
        "082":"Keystone Bank Ltd",
        "014":"Mainstreet Bank Plc",
        "076":"Skye Bank Plc",
        "039":"Stanbic IBTC Plc",
        "232":"Sterling Bank Plc",
        "032":"Union Bank Nigeria Plc",
        "033":"United Bank of Africa Plc",
        "215":"Unity Bank Plc",
        "035":"WEMA Bank Plc",
        "057":"Zenith Bank International",
        "101":"Providus Bank",
        "104":"PARALLEX BANK LIMITED",
        "303":"LOTUS BANK LIMITED",
        "105":"PREMIUM TRUST BANK LTD",
        "106":"SIGNATURE BANK LTD",
        "103":"GLOBUS BANK",
        "102":"TITAN TRUST BANK",
        "067":"Polaris Bank",
        "107":"OPTIMUS BANK LTD",
        "068":"Standard Chartered Bank",
        "100":"Suntrust Bank",
    }

    user_bank_name = user_bank_name.lower().strip()

    for code, name in banks.items():
        name_clean = name.lower().strip()
        
        # Remove Plc, Ltd, Limited at the end
        for suffix in [" plc", " ltd", " limited"]:
            if name_clean.endswith(suffix):
                name_clean = name_clean[:-len(suffix)].strip()
        
        # Check if user's input is in the bank name
        if user_bank_name in name_clean:
            return code

    return None  # if no match found
    
