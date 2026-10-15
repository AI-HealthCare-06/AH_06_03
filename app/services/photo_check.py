"""사진 파일 확인: JPEG인지, 크기가 허용 범위인지, 촬영 위치(GPS) 정보가 들어 있지 않은지.
화면이 사진을 다시 그려서 올리므로 위치 정보가 빠지지만, API로 직접 올리는 경우를 막기 위해 서버도 확인한다."""
import struct

MAX_BYTES = 300 * 1024          # 사진 한 장
MAX_PHOTOS = 3                  # 글 하나
GPS_TAG = 0x8825                # EXIF에서 촬영 위치를 가리키는 항목
EXIF_HEAD = b"Exif\x00\x00"


def is_jpeg(data: bytes) -> bool:
    return len(data) > 4 and data[:3] == b"\xff\xd8\xff"


def has_location(data: bytes) -> bool:
    """JPEG 안의 EXIF(APP1)에 GPS 항목이 있으면 True. EXIF가 없거나 깨져 있으면 False."""
    i, n = 2, len(data)
    while i + 4 <= n and data[i] == 0xFF:
        marker = data[i + 1]
        if marker in (0xDA, 0xD9):                       # 이미지 데이터가 시작되면 머리 부분은 끝
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:    # 길이가 없는 표식
            i += 2
            continue
        size = struct.unpack(">H", data[i + 2:i + 4])[0]
        seg = data[i + 4:i + 2 + size]
        if marker == 0xE1 and seg[:6] == EXIF_HEAD and _tiff_has_gps(seg[6:]):
            return True
        i += 2 + size
    return False


def _tiff_has_gps(t: bytes) -> bool:
    if len(t) < 8 or t[:2] not in (b"II", b"MM"):
        return False
    e = "<" if t[:2] == b"II" else ">"
    try:
        ifd, seen = struct.unpack(e + "I", t[4:8])[0], 0
        while ifd and ifd + 2 <= len(t) and seen < 2:    # IFD0·IFD1만 본다 (GPS 가리킴은 IFD0에 있다)
            count = struct.unpack(e + "H", t[ifd:ifd + 2])[0]
            for k in range(count):
                off = ifd + 2 + 12 * k
                if off + 12 > len(t):
                    return False
                if struct.unpack(e + "H", t[off:off + 2])[0] == GPS_TAG:
                    return True
            nxt = ifd + 2 + 12 * count
            ifd = struct.unpack(e + "I", t[nxt:nxt + 4])[0] if nxt + 4 <= len(t) else 0
            seen += 1
    except struct.error:
        return False
    return False
