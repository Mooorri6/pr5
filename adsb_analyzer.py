import re
import math
import pyModeS as pms
from datetime import datetime

# Константы
THRESHOLDS = {
    'delay_max': 0.5,        # максимальная задержка
    'coord_error': 100,       # ошибка координат в метрах
    'speed_error': 2,         # ошибка скорости в узлах
    'heading_error': 2,       # ошибка курса в градусах
    'altitude_error': 2000,   # ошибка высоты в футах
    'min_coord_value': 0.0001 # минимальное значение координат
}

class ADSBMessage:
    def __init__(self, timestamp, msg_type='OTHER'):
        self.timestamp = timestamp
        self.type = msg_type
        self.lat = None
        self.lon = None
        self.alt = None
        self.ew_vel = None
        self.ns_vel = None
        self.heading = None
        self.speed_valid = False
        self.ew_dir = None
        self.ns_dir = None
        # сырые данные
        self.raw_msg = None
        self.is_even = None

class ADSBError:
    """Класс для хранения ошибок"""
    def __init__(self, error_type, time, **kwargs):
        self.type = error_type
        self.time = time
        for key, value in kwargs.items():
            setattr(self, key, value)

class ADSBAnalyzer:
    
    def __init__(self, icao_address):
        self.icao = icao_address
        self.input_messages = []
        self.output_messages = []
        self.delays = []
        self.errors = []
        # Хранилище для декодирования
        self.cpr_messages = {'even': None, 'odd': None}
        self.decoded_count = 0
    
    def parse_log_file(self, filename):
        print(f"\nЗагрузка данных: {filename}")
        print(f"Поиск сообщений для ICAO: {self.icao}")
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if 'process_adsb_in_message' in line and self.icao in line:
                        self._parse_input_message(line)
                    elif 'send_pivo_msg' in line and self.icao in line:
                        self._parse_output_message(line)
        
        except FileNotFoundError:
            print(f"Ошибка: Файл {filename} не найден")
            return
        
        print(f"Найдено входных сообщений: {len(self.input_messages)}")
        print(f"Найдено выходных донесений: {len(self.output_messages)}")
        print(f"Декодировано координат: {self.decoded_count}")
        
        self._analyze_delays()
        self._analyze_parameters()
    
    def _parse_input_message(self, line):

        timestamp = self._extract_timestamp(line)
        if timestamp is None:
            return
        
        msg = ADSBMessage(timestamp)
        
        raw_match = re.search(r'8D[A-F0-9\s]{20,}', line)
        if raw_match:
            raw_with_spaces = raw_match.group(0)

            clean_msg = raw_with_spaces.replace(' ', '')[:28]
            if len(clean_msg) == 28:
                msg.raw_msg = clean_msg
        
        if 'TYPE 11' in line or 'TYPE 18' in line:
            self._parse_type11(line, msg)
            if msg.raw_msg:
                self._decode_position_pymodes(msg)
        elif 'TYPE 19' in line:
            self._parse_type19(line, msg)
        elif 'TYPE 29' in line:
            self._parse_type29(line, msg)
        elif 'TYPE 4' in line:
            msg.type = 'TYPE_4'
        elif 'TYPE 31' in line or 'F8210002' in line:
            msg.type = 'TYPE_31'
        
        self.input_messages.append(msg)
    
    def _decode_position_pymodes(self, msg):
        try:
            df = pms.df(msg.raw_msg)
            if df != 17:
                return
            
            tc = pms.adsb.typecode(msg.raw_msg)
            
            if 5 <= tc <= 18 or 20 <= tc <= 22:
                is_even = pms.adsb.oe_flag(msg.raw_msg)
                msg.is_even = is_even
                
                cpr_msg = {
                    'msg': msg.raw_msg,
                    'time': msg.timestamp,
                    'is_even': is_even
                }
                
                if is_even:
                    self.cpr_messages['even'] = cpr_msg
                else:
                    self.cpr_messages['odd'] = cpr_msg
                
                alt = pms.adsb.altitude(msg.raw_msg)
                if alt is not None:
                    msg.alt = alt
                
                if self.cpr_messages['even'] and self.cpr_messages['odd']:
                    even = self.cpr_messages['even']
                    odd = self.cpr_messages['odd']
                    
                    if abs(even['time'] - odd['time']) < 10:
                        lat, lon = pms.adsb.position(
                            even['msg'], odd['msg'],
                            even['time'], odd['time']
                        )
                        
                        if lat is not None and lon is not None:
                            msg.lat = lat
                            msg.lon = lon
                            self.decoded_count += 1
                            print(f"  Декодированы координаты: {lat:.6f}, {lon:.6f}, высота: {msg.alt} ft")
        
        except Exception as e:
            pass
    
    def _parse_output_message(self, line):
        timestamp = self._extract_timestamp(line)
        if timestamp is None:
            return
        
        msg = ADSBMessage(timestamp)
        
        if 'SVR_STRUCT' in line:
            self._parse_svr_struct(line, msg)
        elif 'MSR_STRUCT' in line:
            msg.type = 'MSR_STRUCT'
        elif 'TSR_STRUCT' in line:
            msg.type = 'TSR_STRUCT'
        
        self.output_messages.append(msg)
    
    def _extract_timestamp(self, line):
        match = re.match(r'^(\d+\.\d+)', line)
        return float(match.group(1)) if match else None
    
    def _parse_type11(self, line, msg):
        msg.type = 'TYPE_11'
        
        lat_match = re.search(r'lat\s+([0-9\-\.]+)', line, re.IGNORECASE)
        lon_match = re.search(r'lon\s+([0-9\-\.]+)', line, re.IGNORECASE)
        alt_match = re.search(r'ALT\s+(\d+)\s+ft', line)
        
        if lat_match and lon_match:
            msg.lat = float(lat_match.group(1))
            msg.lon = float(lon_match.group(1))
        
        if alt_match:
            msg.alt = int(alt_match.group(1))
    
    def _parse_type19(self, line, msg):
        msg.type = 'TYPE_19'
        
        ew_match = re.search(r'EW_VEL\s+(\d+)\s+kt', line)
        ns_match = re.search(r'NS_VEL\s+(\d+)\s+kt', line)
        
        if 'EW_DIR EAST' in line:
            msg.ew_dir = 'EAST'
        elif 'EW_DIR WEST' in line:
            msg.ew_dir = 'WEST'
        
        if 'NS_DIR SOUTH' in line:
            msg.ns_dir = 'SOUTH'
        elif 'NS_DIR NORTH' in line:
            msg.ns_dir = 'NORTH'
        
        if ew_match:
            msg.ew_vel = int(ew_match.group(1))
        if ns_match:
            msg.ns_vel = int(ns_match.group(1))
            msg.speed_valid = True
    
    def _parse_type29(self, line, msg):

        msg.type = 'TYPE_29'
        hdg_match = re.search(r'SEL_HDG\s+([0-9\.]+)\s+deg', line)
        if hdg_match:
            msg.heading = float(hdg_match.group(1))
    
    def _parse_svr_struct(self, line, msg):
        msg.type = 'SVR_STRUCT'
        
        lat_match = re.search(r'LAT\s+([0-9\-\.]+)', line)
        lon_match = re.search(r'LON\s+([0-9\-\.]+)', line)
        alt_match = re.search(r'GEO_ALT\s+([0-9\-\.]+)\s+ft', line)
        ns_match = re.search(r'NSV\s+([0-9\-]+)', line)
        ew_match = re.search(r'EWV\s+(\d+)', line)
        
        if lat_match:
            msg.lat = float(lat_match.group(1))
        if lon_match:
            msg.lon = float(lon_match.group(1))
        if alt_match:
            msg.alt = float(alt_match.group(1))
        if ns_match:
            msg.ns_vel = int(ns_match.group(1))
            msg.speed_valid = True
        if ew_match:
            msg.ew_vel = int(ew_match.group(1))
    
    def _analyze_delays(self):
        print("\nАнализ задержек -")
        
        for out_msg in self.output_messages:
            if out_msg.type != 'SVR_STRUCT':
                continue
            
            last_in = None
            for in_msg in self.input_messages:
                if (in_msg.type == 'TYPE_11' and 
                    in_msg.timestamp <= out_msg.timestamp):
                    if (last_in is None or 
                        in_msg.timestamp > last_in.timestamp):
                        last_in = in_msg
            
            if last_in:
                delay = out_msg.timestamp - last_in.timestamp
                if delay < 1.0:
                    self.delays.append({
                        'time': out_msg.timestamp,
                        'delay': delay
                    })
        
        if self.delays:
            delays_ms = [d['delay'] * 1000 for d in self.delays]
            print(f"Задержек: {len(self.delays)}, "
                  f"средняя: {sum(delays_ms)/len(delays_ms):.1f} мс")
    
    def _analyze_parameters(self):
        """Анализ параметров"""
        print("\nПроверка параметров -")
        
        for out_msg in self.output_messages:
            if out_msg.type != 'SVR_STRUCT':
                continue
            
            in_11 = self._find_closest_input(out_msg.timestamp, 'TYPE_11')
            in_19 = self._find_closest_input(out_msg.timestamp, 'TYPE_19')
            
            if in_11:
                self._check_coordinate_errors(out_msg, in_11)
                self._check_altitude_errors(out_msg, in_11)
            
            if in_19 and out_msg.speed_valid:
                self._check_speed_errors(out_msg, in_19)
                self._check_heading_errors(out_msg, in_19)
        
        error_counts = {}
        for err in self.errors:
            error_counts[err.type] = error_counts.get(err.type, 0) + 1
        
        for err_type, count in error_counts.items():
            print(f"  {err_type}: {count} ошибок")
    
    def _find_closest_input(self, out_time, msg_type, max_diff=0.5):

        best = None
        min_diff = float('inf')
        
        for in_msg in self.input_messages:
            if in_msg.type != msg_type:
                continue
            if in_msg.timestamp <= out_time:
                diff = out_time - in_msg.timestamp
                if diff < max_diff and diff < min_diff:
                    min_diff = diff
                    best = in_msg
        return best
    
    def _calculate_heading(self, msg, is_svr=False):
        """Расчет курса"""
        if msg.ew_vel is None or msg.ns_vel is None:
            return None
        
        try:
            if is_svr:
                return math.degrees(math.atan2(msg.ew_vel, msg.ns_vel)) % 360
            else:
                ew_signed = msg.ew_vel
                if msg.ew_dir == 'WEST':
                    ew_signed = -msg.ew_vel
                
                ns_signed = msg.ns_vel
                if msg.ns_dir == 'NORTH':
                    ns_signed = -msg.ns_vel
                elif msg.ns_dir == 'SOUTH':
                    ns_signed = msg.ns_vel
                
                return math.degrees(math.atan2(ew_signed, -ns_signed)) % 360
        except (TypeError, ValueError):
            return None
    
    def _check_coordinate_errors(self, out_msg, in_msg):
        """Проверка ошибок координат"""
        if (in_msg.lat is None or in_msg.lon is None or 
            out_msg.lat is None or out_msg.lon is None):
            return
        
        try:
            if (abs(in_msg.lat) < THRESHOLDS['min_coord_value'] or 
                abs(in_msg.lon) < THRESHOLDS['min_coord_value']):
                return
            
            lat_diff = abs(out_msg.lat - in_msg.lat) * 111000
            lon_diff = abs(out_msg.lon - in_msg.lon) * 111000 * \
                      math.cos(math.radians(out_msg.lat))
            
            if lat_diff > THRESHOLDS['coord_error'] or lon_diff > THRESHOLDS['coord_error']:
                self.errors.append(ADSBError(
                    'coord', out_msg.timestamp,
                    lat_diff=lat_diff,
                    lon_diff=lon_diff
                ))
        except (TypeError, ValueError):
            pass
    
    def _check_speed_errors(self, out_msg, in_msg):
        """Проверка ошибок скорости"""
        if (in_msg.ew_vel is None or in_msg.ns_vel is None or
            out_msg.ew_vel is None or out_msg.ns_vel is None):
            return
        
        try:
            speed_in = math.hypot(in_msg.ew_vel, in_msg.ns_vel)
            speed_out = math.hypot(out_msg.ew_vel, out_msg.ns_vel)
            speed_diff = abs(speed_out - speed_in)
            
            if speed_diff > THRESHOLDS['speed_error']:
                self.errors.append(ADSBError(
                    'speed', out_msg.timestamp,
                    diff=speed_diff
                ))
        except (TypeError, ValueError):
            pass
    
    def _check_heading_errors(self, out_msg, in_msg):
        """Проверка ошибок курса"""
        heading_in = self._calculate_heading(in_msg)
        heading_out = self._calculate_heading(out_msg, is_svr=True)
        
        if heading_in is not None and heading_out is not None:
            try:
                hdg_diff = abs(heading_out - heading_in)
                hdg_diff = min(hdg_diff, 360 - hdg_diff)
                
                if hdg_diff > THRESHOLDS['heading_error']:
                    self.errors.append(ADSBError(
                        'heading', out_msg.timestamp,
                        diff=hdg_diff,
                        in_val=heading_in,
                        out_val=heading_out
                    ))
            except (TypeError, ValueError):
                pass
    
    def _check_altitude_errors(self, out_msg, in_msg):
        """Проверка ошибок высоты"""
        if in_msg.alt is None or out_msg.alt is None:
            return
        
        try:
            alt_diff = abs(out_msg.alt - in_msg.alt)
            
            if alt_diff > THRESHOLDS['altitude_error']:
                self.errors.append(ADSBError(
                    'altitude', out_msg.timestamp,
                    diff=alt_diff,
                    baro=in_msg.alt,
                    geo=out_msg.alt
                ))
        except (TypeError, ValueError):
            pass