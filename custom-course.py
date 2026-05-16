import os
import re
import random
from pathlib import Path

# --- CONFIGURATION ---
SONGS_DIR = Path("\\\\nas\\media\\Stepmania\\Songs")
OUTPUT_DIR = Path("\\\\nas\\media\\Stepmania\\Courses\\Cardio Workout")
TARGET_MIN_NPS = 2.5
TARGET_MAX_NPS = 4.0
MAX_JUMP_PERCENTAGE = 0.07
MAX_MINE_PERCENTAGE = 0.10  # Restrict charts that use mines as artificial density
MIN_SONG_DURATION = 80 
MAX_SONG_DURATION = 360  # Hard limit: Reject any individual song longer than 6 minutes

# --- AUDIT ENGINE ---
# Add substrings of titles you want to track to debug why they are failing/passing
AUDIT_LIST = ["POP STARS", "Go Getters", "DO U", "Rebellion"]
audit_report = []
def parse_msd(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    content = re.sub(r'//.*', '', content)
    # Use non-greedy matching to prevent metadata fields from absorbing chart bodies
    return re.findall(r'#([^:]+):(.*?);', content, re.DOTALL)

def robust_ssc_parser(file_path: str):
    charts = {}
    current_chart = {}
    inside_note_block = False
    note_buffer = []

    # Regex to clean up inline comments and hidden unicode characters
    clean_pattern = re.compile(r'[\xa0\s]*//.*$')

    # Fast-reject native .sm structures so they step down to the legacy regex engine
    if Path(file_path).suffix.lower() == '.sm':
        return {}
    # ----------------------

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            cleaned = clean_pattern.sub('', line).strip()

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            cleaned = clean_pattern.sub('', line).strip()
            if not cleaned:
                continue

            # 1. Initialize empty dictionary at the true boundary tag
            if cleaned == '#NOTEDATA:;':
                current_chart = {'metadata': {}}
                continue

            if cleaned == '#CHARTNAME:;':
                continue

            if inside_note_block:
                if cleaned == ';':
                    inside_note_block = False
                    current_chart['notes'] = "".join(note_buffer)
                    # 2. Extract key when saving, handle files that lack explicit values Safely
                    diff_key = current_chart.get('difficulty', 'Unknown')
                    charts[diff_key] = current_chart
                    note_buffer = []
                else:
                    note_buffer.append(cleaned + '\n')
                continue

            if cleaned.startswith('#') and ':' in cleaned:
                tag_content = cleaned[1:].rstrip(';')
                tag_name, _, tag_value = tag_content.partition(':')
                
                tag_name = tag_name.upper()
                if tag_name == 'NOTES':
                    inside_note_block = True
                elif tag_name == 'DIFFICULTY':
                    current_chart['difficulty'] = tag_value
                elif current_chart and tag_name in ['METER', 'STEPSTYPE', 'CREDIT', 'CHARTNAME']:
                    current_chart['metadata'][tag_name] = tag_value

    return charts

def calculate_duration(bpm_string, stops_string, total_measures):
    if not bpm_string: return 0
    bpms = []
    for pair in bpm_string.split(','):
        if '=' in pair:
            b, b_val = pair.split('=')
            bpms.append((float(b), float(b_val)))
    stops = []
    if stops_string:
        for pair in stops_string.split(','):
            if '=' in pair:
                b, s_val = pair.split('=')
                stops.append((float(b), float(s_val)))
                
    total_beats = total_measures * 4
    duration = 0.0
    current_beat = 0.0
    current_bpm = bpms[0][1] if bpms else 120
    bpm_index = 1
    
    while current_beat < total_beats:
        next_change_beat = total_beats
        if bpm_index < len(bpms):
            next_change_beat = bpms[bpm_index][0]
        target_beat = min(next_change_beat, total_beats)
        beat_delta = target_beat - current_beat
        if current_bpm > 0:
            duration += (beat_delta * 60.0) / current_bpm
        current_beat = target_beat
        if next_change_beat == target_beat and bpm_index < len(bpms):
            current_bpm = bpms[bpm_index][1]
            bpm_index += 1
    for stop_beat, stop_time in stops:
        if stop_beat < total_beats:
            duration += stop_time
    return duration

def analyze_chart_advanced(chart_data, duration_est):
    measures = chart_data.split(',')
    total_notes = 0
    jumps = 0
    mines = 0
    measure_note_counts = []
    
    for measure in measures:
        lines = [line.strip() for line in measure.split('\n') if line.strip()]
        measure_notes = 0
        for line in lines:
            if line.isdigit() or 'M' in line:
                step_count = line.count('1') + line.count('2') + line.count('4')
                mines += line.count('M')
                if step_count > 0:
                    measure_notes += 1
                if step_count > 1:
                    jumps += 1
        total_notes += measure_notes
        measure_note_counts.append(measure_notes)
                    
    if total_notes == 0:
        return 0, 0, 0, False
        
    jump_ratio = jumps / total_notes
    mine_ratio = mines / total_notes
    
    total_measures = len(measures)
    if total_measures == 0: return 0, 0, 0, False
    
    seconds_per_measure = duration_est / total_measures
    measures_in_10s = max(1, int(10 / seconds_per_measure))
    
    for i in range(0, len(measure_note_counts), measures_in_10s):
        window_notes = sum(measure_note_counts[i:i+measures_in_10s])
        window_duration = min(10, (len(measure_note_counts[i:i+measures_in_10s]) * seconds_per_measure))
        if window_duration > 0:
            window_nps = window_notes / window_duration
            if window_nps > (TARGET_MAX_NPS * 1.25):
                return total_notes, jump_ratio, mine_ratio, False
                
    return total_notes, jump_ratio, mine_ratio, True

def main():
    try:
        workout_mins = float(input("Enter target workout duration per set (in minutes): "))
        target_set_duration = workout_mins * 60
    except ValueError:
        target_set_duration = 45 * 60

    print("Locating stepchart files...")
    all_files = list(SONGS_DIR.glob('**/*.sm')) + list(SONGS_DIR.glob('**/*.ssc'))
    ssc_directories = {f.parent for f in all_files if f.suffix == '.ssc'}
    
    filtered_files = []
    for f in all_files:
        # Reject files in hidden AppleDouble resource directories or macOS shadow files
        if ".AppleDouble" in f.parts or f.name.startswith("._"):
            continue
        if f.suffix == '.sm' and f.parent in ssc_directories:
            continue
        filtered_files.append(f)
        
    total_files = len(filtered_files)
    matching_pool = []
    added_charts = set()

    print(f"Analyzing {total_files} files...")
    for index, sm_file in enumerate(filtered_files, start=1):
        percent = (index / total_files) * 100
        bar = '#' * int(percent // 2) + '-' * (50 - int(percent // 2))
        print(f"\r[{bar}] {percent:.1f}% ({index}/{total_files})", end='', flush=True)
        
        try:
            tags = parse_msd(sm_file)
            metadata = {k.strip().upper(): v.strip() for k, v in tags}
            
            title = metadata.get('TITLE', sm_file.parent.name)
            group_name = sm_file.parent.parent.name
            song_folder_name = sm_file.parent.name
            
            bpm_str = metadata.get('BPMS', '')
            stops_str = metadata.get('STOPS', '')
            
            is_audited = any(a_title.lower() in title.lower() for a_title in AUDIT_LIST)
            ssc_charts = robust_ssc_parser(str(sm_file))
            
            processed_charts = []
            if ssc_charts:
                for diff_name, chart_obj in ssc_charts.items():
                    processed_charts.append({
                        'style': chart_obj['metadata'].get('STEPSTYPE', '').strip(),
                        'difficulty': diff_name,
                        'data': chart_obj['notes'].strip()
                    })
            else:
                with open(sm_file, 'r', encoding='utf-8', errors='ignore') as f:
                    raw = f.read()
                
                # Strip comments clean line-by-line first to prevent semicolon token bugs
                cleaned_lines = [line.split('//', 1)[0] for line in raw.splitlines()]
                cleaned_raw = '\n'.join(cleaned_lines)
                
                # Case-insensitive block selector matching any spacing variation
                note_blocks = re.findall(r'#NOTES\s*:\s*(.*?);', cleaned_raw, re.DOTALL | re.IGNORECASE)
                
                for block in note_blocks:
                    # Enforce strict 5-cut maxsplit to isolate parameters from trailing data
                    lines = block.split(':', 5)
                    if len(lines) < 6: 
                        continue
                    processed_charts.append({
                        'style': lines[0].strip(),
                        'difficulty': lines[2].strip(),
                        'data': lines[5].strip()
                    })

            if is_audited and not processed_charts:
                audit_report.append(f"REJECTED: '{title}' - No parseable charts resolved.")

            if not processed_charts:
                print(f"\nFAILED TO PARSE: {sm_file.name} (Structure corrupt or unhandled format)")
                continue

            for chart in processed_charts:
                style = chart['style']
                difficulty_name = chart['difficulty']
                chart_data = chart['data']
                
                if style != "dance-single": continue
                    
                notes, jump_ratio, mine_ratio, passes_window_test = analyze_chart_advanced(chart_data, calculate_duration(bpm_str, stops_str, len(chart_data.split(','))))
                duration_est = calculate_duration(bpm_str, stops_str, len(chart_data.split(',')))
                
                if duration_est == 0: continue
                nps = notes / duration_est
                
                fail_reasons = []
                if not (TARGET_MIN_NPS <= nps <= TARGET_MAX_NPS):
                    fail_reasons.append(f"Global NPS out of bounds ({nps:.2f})")
                if jump_ratio > MAX_JUMP_PERCENTAGE:
                    fail_reasons.append(f"Jump ratio too high ({jump_ratio*100:.1f}%)")
                if mine_ratio > MAX_MINE_PERCENTAGE:
                    fail_reasons.append(f"Mine content too high ({mine_ratio*100:.1f}%)")
                if not passes_window_test:
                    fail_reasons.append("Localized spike detected (failed rolling window check)")
                if duration_est < MIN_SONG_DURATION:
                    fail_reasons.append(f"Duration too short ({duration_est:.0f}s)")
                    
                chart_signature = f"{group_name}/{song_folder_name}:{difficulty_name}"
                
                if is_audited:
                    audit_report.append(f"AUDIT '{title}' [{difficulty_name}] -> NPS: {nps:.2f}, Jumps: {jump_ratio*100:.1f}%, Mines: {mine_ratio*100:.1f}%. Status: {'PASSED' if not fail_reasons else 'FAILED because ' + ', '.join(fail_reasons)}")
                
                if not fail_reasons:
                    if chart_signature in added_charts: continue
                    added_charts.add(chart_signature)
                    matching_pool.append({
                        'group': group_name,
                        'folder_name': song_folder_name,
                        'diff': difficulty_name,
                        'duration': duration_est,
                        'nps': nps,
                        'jumps': jump_ratio,
                        'mines': mine_ratio
                    })
        except Exception as e:
            if is_audited:
                audit_report.append(f"ERROR: Caught exception processing '{title}': {str(e)}")
            continue

    print("\n\n--- AUDIT REPORT ENGINE ---")
    for report in set(audit_report):
        print(report)
    print("---------------------------\n")

    if not matching_pool:
        print("No tracks survived filtration.")
        return

    filtered_pool = [song for song in matching_pool if song['duration'] <= MAX_SONG_DURATION]
    random.shuffle(filtered_pool)

    set_index = 1
    current_set_duration = 0
    current_set_entries = []
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for item in filtered_pool:
        if current_set_duration + item['duration'] > target_set_duration and current_set_entries:
            course_file = OUTPUT_DIR / f"Cardio_Workout_Set_{set_index}.crs"
            with open(course_file, 'w', encoding='utf-8') as f:
                f.write(f"#COURSE:[Cardio Workout] Set {set_index:02d};\n")
                f.write("#GROUP:Cardio Workouts;\n")
                f.write("#BACKGROUND:inline;\n")
                f.write("#BANNER:inline;\n\n")
                for entry in current_set_entries:
                    f.write(f"// METRICS -> NPS: {entry['nps']:.2f} | Jumps: {entry['jumps']*100:.1f}% | Mines: {entry['mines']*100:.1f}% | Len: {entry['duration']:.0f}s\n")
                    f.write(f"#SONG:{entry['group']}/{entry['folder_name']}:{entry['diff']};\n")
            print(f"Generated: {course_file.name} ({current_set_duration / 60:.1f} mins)")
            
            set_index += 1
            current_set_duration = 0
            current_set_entries = []
            
        current_set_entries.append(item)
        current_set_duration += item['duration']

    if current_set_entries:
        course_file = OUTPUT_DIR / f"Cardio_Workout_Set_{set_index}.crs"
        with open(course_file, 'w', encoding='utf-8') as f:
            f.write(f"#COURSE:[Cardio Workout] Set {set_index:02d} (Short);\n")
            f.write("#GROUP:Cardio Workouts;\n")
            f.write("#BACKGROUND:inline;\n")
            f.write("#BANNER:inline;\n\n")
            for entry in current_set_entries:
                f.write(f"// METRICS -> NPS: {entry['nps']:.2f} | Jumps: {entry['jumps']*100:.1f}% | Mines: {entry['mines']*100:.1f}% | Len: {entry['duration']:.0f}s\n")
                f.write(f"#SONG:{entry['group']}/{entry['folder_name']}:{entry['diff']};\n")
        print(f"Generated final partial set: {course_file.name} ({current_set_duration / 60:.1f} mins)")

if __name__ == "__main__":
    main()