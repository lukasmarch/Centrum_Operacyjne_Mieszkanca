/**
 * „w Żabinach”, nie „w Żabiny”. Miejscownik nazw z `alert_policy.GMINA_RYBNO_PLACES`
 * — formy te same, które backend rozpoznaje w komunikatach. Nazwa spoza listy
 * dostaje bezpieczne „w miejscowości X”, bo zgadnięta odmiana jest gorsza niż żadna.
 */
const LOCATIVE: Record<string, string> = {
    'Rybno': 'Rybnie',
    'Dębień': 'Dębieniu',
    'Grabacz': 'Grabaczu',
    'Gralewo': 'Gralewie',
    'Gronowo': 'Gronowie',
    'Groszki': 'Groszkach',
    'Grądy': 'Grądach',
    'Hartowiec': 'Hartowcu',
    'Jeglia': 'Jegli',
    'Kopaniarze': 'Kopaniarzach',
    'Koszelewki': 'Koszelewkach',
    'Koszelewy': 'Koszelewach',
    'Naguszewo': 'Naguszewie',
    'Nowa Wieś': 'Nowej Wsi',
    'Prusy': 'Prusach',
    'Rapaty': 'Rapatach',
    'Rumian': 'Rumianie',
    'Szczupliny': 'Szczuplinach',
    'Truszczyny': 'Truszczynach',
    'Tuczki': 'Tuczkach',
    'Wery': 'Werach',
    'Żabiny': 'Żabinach',
};

export const inPlace = (name: string): string =>
    LOCATIVE[name] ? `w ${LOCATIVE[name]}` : `w miejscowości ${name}`;

/** „o Żabinach” — ta sama forma z przyimkiem „o”. */
export const aboutPlace = (name: string): string =>
    LOCATIVE[name] ? `o ${LOCATIVE[name]}` : `o miejscowości ${name}`;
