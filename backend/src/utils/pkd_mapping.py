from typing import Optional

PKD_SECTIONS = {
    "A": "Rolnictwo, leśnictwo, łowiectwo i rybactwo",
    "B": "Górnictwo i wydobywanie",
    "C": "Przetwórstwo przemysłowe",
    "D": "Wytwarzanie i zaopatrywanie w energię elektryczną, gaz, parę wodną, gorącą wodę i powietrze do układów klimatyzacyjnych",
    "E": "Dostawa wody; gospodarowanie ściekami i odpadami oraz działalność związana z rekultywacją",
    "F": "Budownictwo",
    "G": "Handel hurtowy i detaliczny; naprawa pojazdów samochodowych, włączając motocykle",
    "H": "Transport i gospodarka magazynowa",
    "I": "Działalność związana z zakwaterowaniem i usługami gastronomicznymi",
    "J": "Informacja i komunikacja",
    "K": "Działalność finansowa i ubezpieczeniowa",
    "L": "Działalność związana z obsługą rynku nieruchomości",
    "M": "Działalność profesjonalna, naukowa i techniczna",
    "N": "Działalność w zakresie usług administrowania i działalność wspierająca",
    "O": "Administracja publiczna i obrona narodowa; obowiązkowe zabezpieczenia społeczne",
    "P": "Edukacja",
    "Q": "Opieka zdrowotna i pomoc społeczna",
    "R": "Działalność związana z kulturą, rozrywką i rekreacją",
    "S": "Pozostała działalność usługowa",
    "T": "Gospodarstwa domowe zatrudniające pracowników; gospodarstwa domowe produkujące wyroby i świadczące usługi na własne potrzeby",
    "U": "Organizacje i zespoły eksterytorialne"
}

PKD_DIVISION_MAP = {
    # This is a simplified mapping based on first 2 digits of PKD code
    "01": "A", "02": "A", "03": "A",
    "05": "B", "06": "B", "07": "B", "08": "B", "09": "B",
    "10": "C", "11": "C", "12": "C", "13": "C", "14": "C", "15": "C", "16": "C", "17": "C", "18": "C", "19": "C",
    "20": "C", "21": "C", "22": "C", "23": "C", "24": "C", "25": "C", "26": "C", "27": "C", "28": "C", "29": "C",
    "30": "C", "31": "C", "32": "C", "33": "C",
    "35": "D",
    "36": "E", "37": "E", "38": "E", "39": "E",
    "41": "F", "42": "F", "43": "F",
    "45": "G", "46": "G", "47": "G",
    "49": "H", "50": "H", "51": "H", "52": "H", "53": "H",
    "55": "I", "56": "I",
    "58": "J", "59": "J", "60": "J", "61": "J", "62": "J", "63": "J",
    "64": "K", "65": "K", "66": "K",
    "68": "L",
    "69": "M", "70": "M", "71": "M", "72": "M", "73": "M", "74": "M", "75": "M",
    "77": "N", "78": "N", "79": "N", "80": "N", "81": "N", "82": "N",
    "84": "O",
    "85": "P",
    "86": "Q", "87": "Q", "88": "Q",
    "90": "R", "91": "R", "92": "R", "93": "R",
    "94": "S", "95": "S", "96": "S",
    "97": "T", "98": "T",
    "99": "U"
}

def get_industry_from_pkd(pkd_code: str) -> Optional[str]:
    """
    Map PKD main code (e.g. "62.01.Z") to Industry Name (e.g. "Informacja i komunikacja")
    """
    if not pkd_code:
        return None
    
    # Extract first 2 digits (Division)
    try:
        division = pkd_code[:2]
        section = PKD_DIVISION_MAP.get(division)
        if section:
            return PKD_SECTIONS.get(section)
    except Exception:
        pass
        
    return None
