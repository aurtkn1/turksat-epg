import json
import ssl
import urllib.request
from datetime import datetime, timedelta
from xml.etree.ElementTree import Element, SubElement, ElementTree


# ============================================================
# TÜRKSAT KABLOTV - 7 GÜNLÜK EPG
# ============================================================

BASE_URL = (
    "https://www.turksatkablo.com.tr/"
    "userUpload/EPG/{}.json"
)

OUTPUT_FILE = "epg.xml"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0 Safari/537.36"
)


# ============================================================
# SSL
# ============================================================

# Türksat sunucusunun SSL sertifikası GitHub Actions
# ortamında doğrulanamadığı için sertifika kontrolünü
# devre dışı bırakıyoruz.
SSL_CONTEXT = ssl._create_unverified_context()


# ============================================================
# TÜRKSAT JSON DOSYASINI İNDİR
# ============================================================

def download_json(day):

    url = BASE_URL.format(day)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.turksatkablo.com.tr/",
        },
    )

    print("İndiriliyor:", url)

    with urllib.request.urlopen(
        request,
        timeout=60,
        context=SSL_CONTEXT,
    ) as response:

        content = response.read().decode("utf-8")

    return json.loads(content)


# ============================================================
# XMLTV ZAMAN FORMATINA ÇEVİR
# ============================================================

def xmltv_time(dt):

    return dt.strftime(
        "%Y%m%d%H%M%S +0000"
    )


# ============================================================
# TÜRKSAT YEREL SAATİNİ UTC'YE ÇEVİR
#
# Türksat saatleri Türkiye saati olarak geliyor.
# Türkiye UTC+3 olduğu için 3 saat çıkarıyoruz.
# ============================================================

def parse_time(base_date, time_string):

    hour, minute = map(
        int,
        time_string.split(":")
    )

    local_time = datetime(
        base_date.year,
        base_date.month,
        base_date.day,
        hour,
        minute,
        0,
    )

    return local_time - timedelta(
        hours=3
    )


# ============================================================
# PROGRAM XML'İ OLUŞTUR
# ============================================================

def create_program(
    channel_id,
    title,
    start,
    stop,
):

    programme = Element(
        "programme",
        {
            "start": xmltv_time(start),
            "stop": xmltv_time(stop),
            "channel": channel_id,
        },
    )

    title_element = SubElement(
        programme,
        "title",
        {
            "lang": "tr"
        },
    )

    title_element.text = (
        title
        if title
        else "-"
    )

    return programme


# ============================================================
# ANA İŞLEM
# ============================================================

def main():

    # --------------------------------------------------------
    # BUGÜN
    # --------------------------------------------------------

    today = datetime.now().replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


    # --------------------------------------------------------
    # 7 GÜN OLUŞTUR
    #
    # 0 = bugün
    # 1 = yarın
    # 2 = +2 gün
    # 3 = +3 gün
    # 4 = +4 gün
    # 5 = +5 gün
    # 6 = +6 gün
    # --------------------------------------------------------

    dates = [
        today + timedelta(days=i)
        for i in range(7)
    ]


    all_data = []


    # ========================================================
    # 7 GÜNLÜK TÜRSAT JSON DOSYALARINI İNDİR
    # ========================================================

    for date in dates:

        # ÖNEMLİ:
        #
        # Türksat şu anda:
        #
        # 3.json
        # 4.json
        # 5.json
        #
        # şeklinde kullanıyor.
        #
        # 03.json şeklinde kullanmıyoruz.

        day = str(date.day)


        try:

            data = download_json(
                day
            )


            if not isinstance(
                data,
                dict
            ):

                print(
                    day,
                    ".json geçersiz veri döndürdü."
                )

                continue


            all_data.append(
                (
                    date,
                    data
                )
            )


            print(
                day,
                ".json başarıyla alındı."
            )


        except Exception as error:

            print(
                day,
                ".json alınamadı:",
                error
            )


    # ========================================================
    # HİÇBİR VERİ ALINAMADIYSA DUR
    # ========================================================

    if not all_data:

        raise RuntimeError(
            "Türksat EPG verisi alınamadı."
        )


    # ========================================================
    # XMLTV ANA ETİKETİ
    # ========================================================

    tv = Element(
        "tv",
        {
            "generator-info-name":
                "Türksat KabloTV 7 Günlük EPG",

            "generator-info-url":
                "https://www.turksatkablo.com.tr/",
        },
    )


    # ========================================================
    # KANALLAR
    # ========================================================

    channels = {}


    # ========================================================
    # TÜM KANALLARI OLUŞTUR
    # ========================================================

    for base_date, data in all_data:

        items = data.get(
            "k",
            []
        )


        if not isinstance(
            items,
            list
        ):

            continue


        for item in items:

            if not isinstance(
                item,
                dict
            ):

                continue


            internal_id = item.get(
                "i"
            )

            name = item.get(
                "n",
                ""
            )


            if internal_id is None:

                continue


            if not name:

                continue


            internal_id = str(
                internal_id
            )


            # Aynı kanal farklı günlerde
            # tekrar oluşturulmasın.

            if internal_id in channels:

                continue


            # ------------------------------------------------
            # KANAL ID
            # ------------------------------------------------

            channel_id = (
                "turksatkablo-"
                + internal_id
            )


            channels[internal_id] = {
                "id": channel_id,
                "name": name,
            }


            # ------------------------------------------------
            # CHANNEL
            # ------------------------------------------------

            channel = SubElement(
                tv,
                "channel",
                {
                    "id": channel_id
                },
            )


            # ------------------------------------------------
            # DISPLAY NAME
            # ------------------------------------------------

            display_name = SubElement(
                channel,
                "display-name",
                {
                    "lang": "tr"
                },
            )

            display_name.text = name


    # ========================================================
    # PROGRAMLARI OLUŞTUR
    # ========================================================

    program_count = 0


    for base_date, data in all_data:

        items = data.get(
            "k",
            []
        )


        if not isinstance(
            items,
            list
        ):

            continue


        for item in items:

            if not isinstance(
                item,
                dict
            ):

                continue


            internal_id = item.get(
                "i"
            )


            if internal_id is None:

                continue


            internal_id = str(
                internal_id
            )


            if internal_id not in channels:

                continue


            programs = item.get(
                "p",
                []
            )


            if not isinstance(
                programs,
                list
            ):

                continue


            previous_start = None


            # =================================================
            # KANAL PROGRAMLARI
            # =================================================

            for program in programs:

                if not isinstance(
                    program,
                    dict
                ):

                    continue


                title = program.get(
                    "b",
                    "-"
                )


                start_text = program.get(
                    "c"
                )


                stop_text = program.get(
                    "d"
                )


                if not start_text:

                    continue


                if not stop_text:

                    continue


                # ------------------------------------------------
                # BAŞLANGIÇ VE BİTİŞ
                # ------------------------------------------------

                try:

                    start = parse_time(
                        base_date,
                        start_text
                    )


                    stop = parse_time(
                        base_date,
                        stop_text
                    )


                except Exception:

                    continue


                # ------------------------------------------------
                # GECE YARISINI GEÇEN PROGRAM
                #
                # Örneğin:
                #
                # 23:30 - 01:15
                #
                # ------------------------------------------------

                if stop <= start:

                    stop += timedelta(
                        days=1
                    )


                # ------------------------------------------------
                # SAAT SIRASI KONTROLÜ
                # ------------------------------------------------

                if (
                    previous_start is not None
                    and start < previous_start
                ):

                    start += timedelta(
                        days=1
                    )


                    if stop <= start:

                        stop += timedelta(
                            days=1
                        )


                previous_start = start


                # ------------------------------------------------
                # PROGRAM XML
                # ------------------------------------------------

                programme = create_program(
                    channels[internal_id]["id"],
                    title,
                    start,
                    stop,
                )


                tv.append(
                    programme
                )


                program_count += 1


    # ========================================================
    # XML DOSYASINI KAYDET
    # ========================================================

    tree = ElementTree(
        tv
    )


    # --------------------------------------------------------
    # XML'İ OKUNABİLİR HALE GETİR
    # --------------------------------------------------------

    try:

        import xml.etree.ElementTree as ET

        ET.indent(
            tree,
            space="  "
        )

    except Exception:

        pass


    # --------------------------------------------------------
    # DOSYAYI YAZ
    # --------------------------------------------------------

    tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True,
    )


    # ========================================================
    # SONUÇ
    # ========================================================

    print()
    print(
        "========================================"
    )

    print(
        "7 GÜNLÜK EPG BAŞARIYLA OLUŞTURULDU"
    )

    print(
        "Dosya:",
        OUTPUT_FILE
    )

    print(
        "Kanal sayısı:",
        len(channels)
    )

    print(
        "Program sayısı:",
        program_count
    )

    print(
        "Gün sayısı:",
        len(all_data)
    )

    print(
        "========================================"
    )


# ============================================================
# ÇALIŞTIR
# ============================================================

if __name__ == "__main__":

    main()
