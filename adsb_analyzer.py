import re
import math
import pyModeS as pms

THRESHOLDS = {
    'delay_max': 0.5,        # максимальная задержка (сек)
    'coord_error': 100,       # ошибка координат (м)
    'speed_error': 2,         # ошибка скорости (узлы)
    'heading_error': 2,       # ошибка курса (градусы)
    'altitude_error': 2000,   # ошибка высоты (футы)
    'min_coord_value': 0.0001 # мин. значение координат
}

class ADSBMessage:
    def __init__(self, timestamp, msg_type='OTHER'):
        self.timestamp = timestamp
        self.type = msg_type
        self.lat = None
        self.lon = None
        self.alt = None # баро высота
        self.geo_alt = None # геометрическая высота (TYPE_19 + TYPE_11)
        self.alt_diff = None # разница между гео и баро высотой (TYPE_19)
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
    #хранение ошибок
    def __init__(self, error_type, t, **kwargs):
        self.type = error_type
        self.t = t
        for key, value in kwargs.items():
            setattr(self, key, value)

class ADSBAnalyzer:
    
    def __init__(self, icao_address):
        self.icao = icao_address
        self.input_messages = []
        self.output_messages = []
        self.delays = []
        self.all_changes = []
        self.errors = []
        self.thresholds = THRESHOLDS

        self.cpr_messages = {'even': None, 'odd': None} #декодирование
        self.decoded_c = 0

        self.last_baro_alt = None
        self.last_baro_alt_t = None
    
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
        print(f"Декодировано координат: {self.decoded_c}")
        
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
                            self.decoded_c += 1
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

            self.last_baro_alt = msg.alt
            self.last_baro_alt_t = msg.timestamp
    
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
        
        diff_match = re.search(r'DIF_FROM_BARO_ALT\s+(\d+)\s+ft', line) #разница высот
        if diff_match:
            msg.alt_diff = int(diff_match.group(1))
            
            if 'IS_GEO_ALT_BELOW_BARO ABOVE' in line:
                pass
            elif 'IS_GEO_ALT_BELOW_BARO BELOW' in line:
                msg.alt_diff = -msg.alt_diff
            
            if self.last_baro_alt is not None:
                msg.geo_alt = self.last_baro_alt + msg.alt_diff
    
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
        baro_match = re.search(r'BARO_ALT\s+([0-9\-\.]+)\s+ft', line)
        
        if lat_match:
            msg.lat = float(lat_match.group(1))
        if lon_match:
            msg.lon = float(lon_match.group(1))
        if alt_match:
            msg.geo_alt = float(alt_match.group(1))
        if baro_match:
            msg.alt = float(baro_match.group(1))
        if ns_match:
            msg.ns_vel = int(ns_match.group(1))
            msg.speed_valid = True
        if ew_match:
            msg.ew_vel = int(ew_match.group(1))
    
    def _analyze_delays(self):
        print("\nАнализ задержек -")
        
        last_values = {
            'lat': None, 'lon': None, 
            'baro_alt': None, 'geo_alt': None,
            'ns_vel': None, 'ew_vel': None
        }
        
        changes_count = {
            'lat': 0, 'lon': 0,
            'baro_alt': 0, 'geo_alt': 0,
            'ns_vel': 0, 'ew_vel': 0
        }
        
        delays_count = {
            'lat': 0, 'lon': 0,
            'baro_alt': 0, 'geo_alt': 0,
            'ns_vel': 0, 'ew_vel': 0
        }
        
        # Список задержек
        delays_by_param = {
            'lat': [], 'lon': [], 
            'baro_alt': [], 'geo_alt': [],
            'ns_vel': [], 'ew_vel': []
        }
        
        for out_msg in self.output_messages:
            if out_msg.type != 'SVR_STRUCT':
                continue
            
            out_time = out_msg.timestamp
            
            #широта
            if out_msg.lat is not None:
                best_in = None
                min_time_diff = float('inf')
                
                for in_msg in self.input_messages:
                    if in_msg.timestamp > out_time:
                        continue
                    if in_msg.type != 'TYPE_11':
                        continue
                    if in_msg.lat is None:
                        continue
                    
                    if abs(in_msg.lat - out_msg.lat) < 0.0001:
                        time_diff = out_time - in_msg.timestamp
                        if time_diff < min_time_diff:
                            min_time_diff = time_diff
                            best_in = in_msg
                
                if best_in:
                    if last_values['lat'] is None or abs(out_msg.lat - last_values['lat']) > 0.0001:
                        changes_count['lat'] += 1
                        last_values['lat'] = out_msg.lat
                        
                        delay = out_time - best_in.timestamp
                        
                        self.all_changes.append({
                            'time': out_time,
                            'delay': delay,
                            'param': 'lat',
                            'value': out_msg.lat,
                            'in_time': best_in.timestamp
                        })
                        
                        if delay > THRESHOLDS['delay_max']:
                            delays_count['lat'] += 1
                            delays_by_param['lat'].append(delay * 1000)
                            self.delays.append({
                                'time': out_time,
                                'delay': delay,
                                'param': 'lat',
                                'value': out_msg.lat,
                                'in_time': best_in.timestamp
                            })
            
            #долгота
            if out_msg.lon is not None:
                best_in = None
                min_time_diff = float('inf')
                
                for in_msg in self.input_messages:
                    if in_msg.timestamp > out_time:
                        continue
                    if in_msg.type != 'TYPE_11':
                        continue
                    if in_msg.lon is None:
                        continue
                    
                    if abs(in_msg.lon - out_msg.lon) < 0.0001:
                        time_diff = out_time - in_msg.timestamp
                        if time_diff < min_time_diff:
                            min_time_diff = time_diff
                            best_in = in_msg
                
                if best_in:
                    if last_values['lon'] is None or abs(out_msg.lon - last_values['lon']) > 0.0001:
                        changes_count['lon'] += 1
                        last_values['lon'] = out_msg.lon
                        delay = out_time - best_in.timestamp
                        
                        self.all_changes.append({
                            'time': out_time,
                            'delay': delay,
                            'param': 'lon',
                            'value': out_msg.lon,
                            'in_time': best_in.timestamp
                        })
                        
                        if delay > THRESHOLDS['delay_max']:
                            delays_count['lon'] += 1
                            delays_by_param['lon'].append(delay * 1000)
                            self.delays.append({
                                'time': out_time,
                                'delay': delay,
                                'param': 'lon',
                                'value': out_msg.lon,
                                'in_time': best_in.timestamp
                            })
            
            # баро высота
            if out_msg.alt is not None:
                best_in = None
                min_time_diff = float('inf')
                
                for in_msg in self.input_messages:
                    if in_msg.timestamp > out_time:
                        continue
                    if in_msg.type != 'TYPE_11':
                        continue
                    if in_msg.alt is None:
                        continue
                    
                    if abs(in_msg.alt - out_msg.alt) < 50:
                        time_diff = out_time - in_msg.timestamp
                        if time_diff < min_time_diff:
                            min_time_diff = time_diff
                            best_in = in_msg
                
                if best_in:
                    if last_values['baro_alt'] is None or abs(out_msg.alt - last_values['baro_alt']) > 0.1:
                        changes_count['baro_alt'] += 1
                        last_values['baro_alt'] = out_msg.alt
                        delay = out_time - best_in.timestamp
                        
                        self.all_changes.append({
                            'time': out_time,
                            'delay': delay,
                            'param': 'baro_alt',
                            'value': out_msg.alt,
                            'in_time': best_in.timestamp
                        })
                        
                        if delay > THRESHOLDS['delay_max']:
                            delays_count['baro_alt'] += 1
                            delays_by_param['baro_alt'].append(delay * 1000)
                            self.delays.append({
                                'time': out_time,
                                'delay': delay,
                                'param': 'baro_alt',
                                'value': out_msg.alt,
                                'in_time': best_in.timestamp
                            })
            
            # гео высота
            if out_msg.geo_alt is not None:
                best_in = None
                min_time_diff = float('inf')
                
                for in_msg in self.input_messages:
                    if in_msg.timestamp > out_time:
                        continue
                    if in_msg.type != 'TYPE_19':
                        continue
                    if in_msg.geo_alt is None:
                        continue
                    
                    if abs(in_msg.geo_alt - out_msg.geo_alt) < 50:
                        time_diff = out_time - in_msg.timestamp
                        if time_diff < min_time_diff:
                            min_time_diff = time_diff
                            best_in = in_msg
                
                if best_in:
                    if last_values['geo_alt'] is None or abs(out_msg.geo_alt - last_values['geo_alt']) > 0.1:
                        changes_count['geo_alt'] += 1
                        last_values['geo_alt'] = out_msg.geo_alt
                        delay = out_time - best_in.timestamp
                        
                        self.all_changes.append({
                            'time': out_time,
                            'delay': delay,
                            'param': 'geo_alt',
                            'value': out_msg.geo_alt,
                            'in_time': best_in.timestamp
                        })
                        
                        if delay > THRESHOLDS['delay_max']:
                            delays_count['geo_alt'] += 1
                            delays_by_param['geo_alt'].append(delay * 1000)
                            self.delays.append({
                                'time': out_time,
                                'delay': delay,
                                'param': 'geo_alt',
                                'value': out_msg.geo_alt,
                                'in_time': best_in.timestamp
                            })
            
            # NS скорость
            if out_msg.ns_vel is not None:
                best_in = None
                min_time_diff = float('inf')
                current_abs = abs(out_msg.ns_vel)
                
                for in_msg in self.input_messages:
                    if in_msg.timestamp > out_time:
                        continue
                    if in_msg.type != 'TYPE_19':
                        continue
                    if in_msg.ns_vel is None:
                        continue
                    
                    if abs(abs(in_msg.ns_vel) - current_abs) <= 1:
                        time_diff = out_time - in_msg.timestamp
                        if time_diff < min_time_diff:
                            min_time_diff = time_diff
                            best_in = in_msg
                
                if best_in:
                    if last_values['ns_vel'] is None or current_abs != last_values['ns_vel']:
                        changes_count['ns_vel'] += 1
                        last_values['ns_vel'] = current_abs
                        delay = out_time - best_in.timestamp
                        
                        self.all_changes.append({
                            'time': out_time,
                            'delay': delay,
                            'param': 'ns_vel',
                            'value': out_msg.ns_vel,
                            'abs_value': current_abs,
                            'in_time': best_in.timestamp,
                            'in_value': best_in.ns_vel
                        })
                        
                        if delay > THRESHOLDS['delay_max']:
                            delays_count['ns_vel'] += 1
                            delays_by_param['ns_vel'].append(delay * 1000)
                            self.delays.append({
                                'time': out_time,
                                'delay': delay,
                                'param': 'ns_vel',
                                'value': out_msg.ns_vel,
                                'abs_value': current_abs,
                                'in_time': best_in.timestamp,
                                'in_value': best_in.ns_vel
                            })
            
            #EW скорость
            if out_msg.ew_vel is not None:
                best_in = None
                min_time_diff = float('inf')
                current_abs = abs(out_msg.ew_vel)
                
                for in_msg in self.input_messages:
                    if in_msg.timestamp > out_time:
                        continue
                    if in_msg.type != 'TYPE_19':
                        continue
                    if in_msg.ew_vel is None:
                        continue
                    
                    if abs(abs(in_msg.ew_vel) - current_abs) <= 1:
                        time_diff = out_time - in_msg.timestamp
                        if time_diff < min_time_diff:
                            min_time_diff = time_diff
                            best_in = in_msg
                
                if best_in:
                    if last_values['ew_vel'] is None or current_abs != last_values['ew_vel']:
                        changes_count['ew_vel'] += 1
                        last_values['ew_vel'] = current_abs
                        delay = out_time - best_in.timestamp
                        
                        self.all_changes.append({
                            'time': out_time,
                            'delay': delay,
                            'param': 'ew_vel',
                            'value': out_msg.ew_vel,
                            'abs_value': current_abs,
                            'in_time': best_in.timestamp,
                            'in_value': best_in.ew_vel
                        })
                        
                        if delay > THRESHOLDS['delay_max']:
                            delays_count['ew_vel'] += 1
                            delays_by_param['ew_vel'].append(delay * 1000)
                            self.delays.append({
                                'time': out_time,
                                'delay': delay,
                                'param': 'ew_vel',
                                'value': out_msg.ew_vel,
                                'abs_value': current_abs,
                                'in_time': best_in.timestamp,
                                'in_value': best_in.ew_vel
                            })
        
        param_names = {
            'lat': 'Широта',
            'lon': 'Долгота',
            'baro_alt': 'Барометрическая высота',
            'geo_alt': 'Геометрическая высота',
            'ns_vel': 'Скорость (NS)',
            'ew_vel': 'Скорость (EW)'
        }
        
        print(f"\nСтатистика изменений параметров -")
        for param, count in changes_count.items():
            if count > 0:
                name = param_names.get(param, param)
                print(f"  {name}: {count} изменений")
        
        if self.delays:
            print(f"\nСтатистика задержек -")
            
            for param, delays_ms in delays_by_param.items():
                if delays_ms:
                    name = param_names.get(param, param)
                    min_delay = min(delays_ms)
                    max_delay = max(delays_ms)
                    print(f"  {name}: {len(delays_ms)} задержек, "
                          f"мин {min_delay:.1f} мс, макс {max_delay:.1f} мс")
        else:
            print(f"\n  Задержек не найдено")
        
        
    
    def _analyze_parameters(self):
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
    
    #расчет курса
    def _calculate_heading(self, msg, is_svr=False):
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
    
    #координаты
    def _check_coordinate_errors(self, out_msg, in_msg):
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
    
    # скорость
    def _check_speed_errors(self, out_msg, in_msg):
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
    
    #курс
    def _check_heading_errors(self, out_msg, in_msg):
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
    
    #высота
    def _check_altitude_errors(self, out_msg, in_msg):

        if in_msg.alt is not None and out_msg.alt is not None:
            try:
                alt_diff = abs(out_msg.alt - in_msg.alt)
                if alt_diff > THRESHOLDS['altitude_error']:
                    self.errors.append(ADSBError(
                        'baro_altitude', out_msg.timestamp,
                        diff=alt_diff,
                        in_val=in_msg.alt,
                        out_val=out_msg.alt
                    ))
            except (TypeError, ValueError):
                pass
        
        if out_msg.geo_alt is not None:
            best_in = None
            min_diff = float('inf')
            
            for in_msg in self.input_messages:
                if in_msg.type != 'TYPE_19' or in_msg.geo_alt is None:
                    continue
                if in_msg.timestamp <= out_msg.timestamp:
                    diff = out_msg.timestamp - in_msg.timestamp
                    if diff < 0.5 and diff < min_diff:
                        min_diff = diff
                        best_in = in_msg
            
            if best_in:
                try:
                    alt_diff = abs(out_msg.geo_alt - best_in.geo_alt)
                    if alt_diff > THRESHOLDS['altitude_error']:
                        self.errors.append(ADSBError(
                            'geo_altitude', out_msg.timestamp,
                            diff=alt_diff,
                            in_val=best_in.geo_alt,
                            out_val=out_msg.geo_alt,
                            alt_diff=best_in.alt_diff
                        ))
                except (TypeError, ValueError):
                    pass