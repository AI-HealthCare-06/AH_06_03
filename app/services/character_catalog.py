"""캐릭터 아이템 가격표. 서버가 기준이고, 화면은 GET /v1/characters/items로 받아서 그린다.
가격 0은 기본(무료) 아이템이라 사지 않아도 쓸 수 있다. 시안(CharacterCreate) 기준."""

SLOTS = ["body", "color", "eye", "expr", "face", "head"]   # 몸체, 색, 눈 색, 표정, 얼굴, 머리

# 종류 → [(키, 이름, 가격)]
ITEMS: dict[str, list[tuple[str, str, int]]] = {
    "body": [
        ("mongle", "몽글이", 0), ("bobo", "동글이", 0), ("rabbit", "말랑이", 0), ("cat", "뾰족이", 0),
        ("square", "네모", 30), ("bear", "곰돌이", 40), ("dino", "공룡이", 50), ("ghost", "유령이", 60),
    ],
    "color": [
        ("#AACDDC", "하늘", 0), ("#81A6C6", "파랑", 0), ("#C9BEE6", "라벤더", 0), ("#F0B8C4", "분홍", 0),
        ("#F2C6A8", "살구", 0), ("#F5DE8F", "노랑", 0), ("#CFE3A0", "연두", 0), ("#A9D6C2", "민트", 0),
        ("#F3E3D0", "크림", 0), ("#D2C4B4", "베이지", 0), ("#CBD2D9", "회색", 0), ("#FFFFFF", "흰색", 0),
        ("#F28B82", "코랄", 20), ("#4FB3B3", "청록", 20), ("#9B8AD6", "보라", 20), ("#3E5C8A", "남색", 20),
        ("#E8C14A", "골드", 40),
    ],
    "eye": [   # 눈 색 (검정(기본) 말고는 부드러운 중간 톤): 기본 5개 무료, 3개는 10파이
        ("#243749", "검정", 0), ("#6FA3D8", "파랑", 0), ("#6BB58E", "초록", 0), ("#A9794F", "갈색", 0), ("#9B87D6", "보라", 0),
        ("#E57373", "빨강", 10), ("#F19AB5", "분홍", 10), ("#E0B84C", "금색", 10),
    ],
    "expr": [
        ("basic", "기본", 0), ("smile", "웃음", 0), ("sleepy", "졸림", 0), ("wow", "놀람", 0), ("wink", "윙크", 0),
        ("cry", "눈물", 20), ("angry", "화남", 20), ("heart", "하트", 30), ("sparkle", "반짝", 40),
    ],
    "face": [
        ("none", "없음", 0), ("glasses", "안경", 0), ("shades", "선글라스", 0), ("mask", "마스크", 0),
        ("whiskers", "고양이수염", 20), ("freckles", "주근깨", 20), ("mustache", "콧수염", 30), ("eyepatch", "안대", 40),
    ],
    "head": [
        ("none", "없음", 0), ("sprout", "새싹", 0), ("crown", "왕관", 0), ("bow", "리본", 0),
        ("flower", "꽃", 30), ("star", "별", 40), ("halo", "천사링", 50), ("horns", "뿔", 40), ("party", "고깔", 30),
    ],
}

DEFAULT = {"body": "mongle", "color": "#AACDDC", "eye": "#243749", "expr": "basic", "face": "none", "head": "none"}

PRICE: dict[str, int] = {f"{slot}:{key}": price for slot, items in ITEMS.items() for key, _, price in items}


def item_key(slot: str, key: str) -> str:
    """보유 표와 파이 장부에 쓰는 아이템 이름. 예: body:bear, color:#E8C14A"""
    return f"{slot}:{key}"