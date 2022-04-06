# 1. export youtube audio by adding "pi" youtubepi.com
# 2. detect turntaking with otter.ai and export srt files
# 3. create a folder named srt2otr next to the script
# 4. add srt files to the folder
# 5. run script
# Note: don't rename files till the end!

from collections import defaultdict
from mimetypes import encodings_map
from pathlib import Path
import inspect
import os
from datetime import time, timedelta
from tarfile import ENCODING


def parse_srt(in_file):
    dump = in_file.read_text(encoding="utf-8").strip()
    utts = {}
    speaker = ''
    previous_end = None
    for u in dump.split('\n\n'):
        # detect export format error
        try:
            num, timestamp, utt = u.split('\n')
        except ValueError:
            print("FILE FORMAT ERROR! Please unselect \"Add line breaks automatically\" in otter.ai and export again.")
            exit()

        # utterance number
        num = int(num)

        # parse timestamp
        start, end = timestamp.replace(',', '.').split(' --> ')
        start = time.fromisoformat(start)
        end = time.fromisoformat(end)
        s_delta = timedelta(hours=start.hour, minutes=start.minute, seconds=start.second, microseconds=start.microsecond)
        e_delta = timedelta(hours=end.hour, minutes=end.minute, seconds=end.second, microseconds=end.microsecond)
        if previous_end:
            preceding_pause = s_delta - previous_end
        else:
            preceding_pause = timedelta()
        span = e_delta - s_delta
        previous_end = e_delta

        # parse speaker
        if ': ' in utt:
            speaker, utt = utt.split(': ')

        utts[num] = {'speaker': speaker, 'start': start, 'end': end, 'span': span, 'utt': utt, 'preceding_pause': preceding_pause}
    return utts


def gen_report(parsed):
    significant_pause = 20

    def find_long_pauses():
        treshold = timedelta(seconds=significant_pause)
        total_pause = timedelta()
        pauses = defaultdict(list)
        for num, utt in parsed.items():
            total_pause += utt['preceding_pause']
            if num == 1:
                continue

            if utt['preceding_pause'] > treshold:
                st = utt['start']
                pause_start = timedelta(hours=st.hour, minutes=st.minute, seconds=st.second, microseconds=st.microsecond) - utt['preceding_pause']
                pauses[f"{parsed[num-1]['speaker']}—>{utt['speaker']}"].append((pause_start, utt['preceding_pause']))
        return pauses, total_pause

    def total_time():
        total = timedelta()
        totals = defaultdict(timedelta)
        for num, utt in parsed.items():
            totals[utt['speaker']] += utt['span']

            total += utt['span']
        percents = defaultdict(int)
        for name, t in totals.items():
            percent = int(t.total_seconds() * 100 / total.total_seconds())
            percents[name] = percent
        return totals, percents

    pauses, total_pause = find_long_pauses()
    spoken_total, spoken_percent = total_time()

    # formatting
    total_pause = str(total_pause)[2:str(total_pause).rfind('.')]

    for k, v in pauses.items():
        out = []
        for s, p in v:
            # start
            start = s.total_seconds()
            formatted = str(s)[:str(s).rfind('.')]
            if formatted.startswith('00:'):
                formatted = formatted[3:]
            time_stamp = f'<span class="timestamp" data-timestamp="{start}">{formatted}</span>'

            # pause
            pause = str(p)[2:str(p).rfind('.')]

            out.append(f"{pause} <i>at:</i> {time_stamp}")
        pauses[k] = out

    for k, v in spoken_total.items():
        spoken_total[k] = str(v)[:str(v).rfind('.')]

    for k, v in spoken_percent.items():
        spoken_percent[k] = f'{v}%'

    out = []
    out.append('<b>Total Speaking Time:</b>')
    for name, spok in spoken_total.items():
        out.append(f"{spok} — {spoken_percent[name]}:\t{name}")
    out.append('')

    out.append('<b>Significant Pauses:</b>')
    out.append(f'<i>Total pause time:</i> {total_pause}')

    for names, p in pauses.items():
        out.append(f'<i>{names}</i>')
        for span in p:
            out.append(f'\t{span}')
    out.append('')

    out = '\n'.join(out)
    return out


def gen_blanked_otr_transcript(parsed):
    # <span class=\"timestamp\" data-timestamp=\"seconds.decimals\">minutes:seconds</span>
    out = []
    speaker = ''
    for num, utt in parsed.items():
        s = utt['start']
        start = timedelta(hours=s.hour, minutes=s.minute, seconds=s.second, microseconds=s.microsecond).total_seconds()
        formatted = s.strftime('%H:%M:%S')
        if formatted.startswith('00:'):
            formatted = formatted[3:]
        time_stamp = f'<span class="timestamp" data-timestamp="{start}">{formatted}</span>'

        fill_in = '\u2591'
        talk = ''.join([u if u == ' ' else fill_in for u in utt['utt']]).strip()
        utterance = f"<span>&nbsp;{time_stamp}&nbsp;&nbsp;&nbsp;&nbsp;" \
                    f'{talk}</span>\n'
        if utt['speaker'] != speaker:
            utterance = f"<br /><br />—<b>{utt['speaker']}</b>—" + utterance
            speaker = utt['speaker']
        out.append(utterance)
    return ''.join(out)


def gen_otr_transcript(parsed):
    # <span class=\"timestamp\" data-timestamp=\"seconds.decimals\">minutes:seconds</span>
    out = []
    for num, utt in parsed.items():
        s = utt['start']
        start = timedelta(hours=s.hour, minutes=s.minute, seconds=s.second, microseconds=s.microsecond).total_seconds()
        formatted = s.strftime('%H:%M:%S')
        if formatted.startswith('00:'):
            formatted = formatted[3:]
        time_stamp = f'<span class="timestamp" data-timestamp="{start}">{formatted}</span>'

        talk = utt['speaker'] + utt['utt']
        utterance = f"<span>&nbsp;{time_stamp}&nbsp;" \
                    f'{talk}</span>\n'
        out.append(utterance)
    return ''.join(out)


def convert_srt2otr(in_file, blank=True, report=True, url=None):
    if not url:
        url = ''
    parsed = parse_srt(in_file)
    report_text = ''
    if report:
        report_text = gen_report(parsed)
        report_text = report_text.replace('\n', '<br />').replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')
    if blank:
        otr_transcript = gen_blanked_otr_transcript(parsed)
    else:
        otr_transcript = gen_otr_transcript(parsed)

    otr_transcript = otr_transcript.replace('\n', '')
    total = f"<p>{report_text}</p><br /><p>{otr_transcript}</p>".replace('"', '\\"')
    otr = '{"text": "' + total + '", "media": "' + url + '", "media-time":0.0}'
    f_name = f'{in_file.stem}_blank.otr' if blank else f'{in_file.stem}.otr'
    otr_file = in_file.parent / f_name
    otr_file.write_text(otr, encoding="utf-8")

def getpath():
    # gets script path so script can be run from anywhere
    filename = inspect.getframeinfo(inspect.currentframe()).filename
    path = os.path.dirname(os.path.abspath(filename))
    return path

# TODO
def get_ytid(file_name):
    # get YouTube Video ID
    ytid = file_name
    return ytid


if __name__ == '__main__':
    blank, report = False, False
    in_path = Path(getpath()) / 'srt2otr'
    url = 'www.youtube.com/watch?v=zVO_h74WK3M'
    for f in in_path.glob('*.srt'):
        convert_srt2otr(f, blank=blank, report=report)
