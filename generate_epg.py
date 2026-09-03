import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from xml.etree.ElementTree import Element, SubElement, ElementTree
from xml.sax.saxutils import escape

BASE_URL = "https://www.turksatkablo.com.tr/userUpload/EPG/{}.json"

OUTPUT_FILE = "epg.xml"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0 Safari/537.36"
)


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

    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read().decode("utf-8")

    return json.loads(data)


def xmltv_time(dt):
    # XMLTV standardı UTC zamanı +0000 şeklinde ister.
    return dt.strftime("%Y%m%d%H%M%S +0000")


def create_program(channel_id, title, start, stop):
    programme = Element(
        "programme",
        {
            "start": xmltv_time(start),
            "stop": xmltv_time(stop),
            "channel": channel_id,
        },
    )

    title_element = SubElement(programme, "title", {"lang": "tr"})
    title_element.text = title if title else "-"

    return programme


def parse_time(base_date, time_string):
    hour, minute = map(int, time_string.split(":"))

    # Türksat saatleri Türkiye yerel saati olarak kabul edilir.
    local_time = datetime(
        base_date.year,
        base_date.month,
        base_date.day,
        hour,
        minute,
        0,
    )

    # Türkiye UTC+3.
    return local_time - timedelta(hours=3)


def main():
    today = datetime.now()

    dates = [
        today,
        today + timedelta(days=1),
    ]

    all_data = []

    for date in dates:
        day = date.strftime("%d")

        try:
            data = download_json(day)
            all_data.append((date, data))
        except Exception as e:
            print(f"{day}.json alınamadı:", e)

    if not all_data:
        raise RuntimeError("Hiçbir Türksat EPG dosyası alınamadı.")

    tv = Element(
        "tv",
        {
            "generator-info-name": "Türksat KabloTV GitHub EPG",
            "generator-info-url": "https://www.turksatkablo.com.tr/",
        },
    )

    channels = {}

    # Önce bütün kanalları oluşturuyoruz.
    for base_date, data in all_data:
        if not isinstance(data, dict):
            continue

        items = data.get("k", [])

        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            internal_id = item.get("i")
            name = item.get("n", "")

            if internal_id is None or not name:
                continue

            internal_id = str(internal_id)

            # Aynı kanal farklı günlerde tekrar gelirse
            # yalnızca bir kez oluştur.
            if internal_id not in channels:
                channel_id = f"turksatkablo-{internal_id}"

                channels[internal_id] = {
                    "id": channel_id,
                    "name": name,
                }

                channel = SubElement(
                    tv,
                    "channel",
                    {"id": channel_id},
                )

                display_name = SubElement(
                    channel,
                    "display-name",
                    {"lang": "tr"},
                )

                display_name.text = name

    # Programları oluştur.
    for base_date, data in all_data:
        if not isinstance(data, dict):
            continue

        items = data.get("k", [])

        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            internal_id = item.get("i")

            if internal_id is None:
                continue

            internal_id = str(internal_id)

            if internal_id not in channels:
                continue

            programs = item.get("p", [])

            if not isinstance(programs, list):
                continue

            previous_start = None

            for program in programs:
                if not isinstance(program, dict):
                    continue

                title = program.get("b", "-")
                start_text = program.get("c")
                stop_text = program.get("d")

                if not start_text or not stop_text:
                    continue

                try:
                    start = parse_time(base_date, start_text)
                    stop = parse_time(base_date, stop_text)
                except Exception:
                    continue

                # Türksat'ta örneğin 22:00 → 06:00 gibi
                # gece yarısını geçen yayınlar var.
                if stop <= start:
                    stop += timedelta(days=1)

                # Bazı kanallarda gün içindeki saatler tekrar
                # başladığında tarihi bir gün ileri taşı.
                if previous_start is not None and start < previous_start:
                    start += timedelta(days=1)

                    if stop <= start:
                        stop += timedelta(days=1)

                previous_start = start

                programme = create_program(
                    channels[internal_id]["id"],
                    title,
                    start,
                    stop,
                )

                tv.append(programme)

    tree = ElementTree(tv)

    try:
        import xml.etree.ElementTree as ET

        ET.indent(tree, space="  ")
    except Exception:
        pass

    tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True,
    )

    print()
    print("========================================")
    print("EPG başarıyla oluşturuldu.")
    print("Dosya:", OUTPUT_FILE)
    print("Kanal sayısı:", len(channels))
    print("========================================")


if __name__ == "__main__":
    main()
