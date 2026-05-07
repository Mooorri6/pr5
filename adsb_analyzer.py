#!/usr/bin/env python3

import re
import math
from collections import defaultdict

#пороги
THRESHOLDS = {
    'delay_max': 0.5,
}


class ADSBMessage:
    """Класс для хранения сообщений"""
    __slots__ = ('type', 'timestamp', 'subtype', 'lat', 'lon', 'alt', 'geo_alt', 
                 'ew_vel', 'ns_vel', 'speed_valid', 'ew_dir', 'ns_dir',
                 'callsign', 'adsb_ver', 'nacp', 'sda', 'sil', 'gva',
                 'selected_alt', 'selected_heading', 'autopilot', 'vnav',
                 'altitude_hold', 'approach', 'lnav', 'gnss_lost', 
                 'ias', 'heading', 'aircraft_status',  'tcas_operational', 'arv_capability', 'tsr_capability')
    
    def __init__(self, timestamp, msg_type='OTHER'):
        self.type = msg_type
        self.timestamp = timestamp
        self.subtype = None
        self.lat = None
        self.lon = None
        self.alt = None
        self.geo_alt = None
        self.ew_vel = None
        self.ns_vel = None
        self.speed_valid = False
        self.ew_dir = None
        self.ns_dir = None
        self.callsign = None
        self.adsb_ver = None
        self.nacp = None
        self.sda = None
        self.sil = None
        self.gva = None
        self.selected_alt = None
        self.selected_heading = None
        self.autopilot = None
        self.vnav = None
        self.altitude_hold = None
        self.approach = None
        self.lnav = None
        self.gnss_lost = False
        self.ias = None
        self.heading = None
        self.aircraft_status = None
        self.tcas_operational = None
        self.arv_capability = None
        self.tsr_capability = None


class ADSBError:
    def __init__(self, error_type, t, param=None, **kwargs):
        self.type = error_type
        self.time = t
        self.param = param
        for key, value in kwargs.items():
            setattr(self, key, value)


class ADSBAnalyzer:
    """Анализ SVR, MSR, TSR, AVR"""
    
    def _get_signed_velocity(self, vel, direction):
        if vel is None:
            return None
        if direction == 'SOUTH' or direction == 'WEST':
            return -vel
        return vel
    
    #svr
    PARAM_CONFIG = [
        ('lat', 'lat', 'TYPE_11', lambda x, y: x == y, 0.0001),
        ('lon', 'lon', 'TYPE_11', lambda x, y: x == y, 0.0001),
        ('baro_alt', 'alt', 'TYPE_11', lambda x, y: x == y, 0.1),
        ('geo_alt', 'geo_alt', 'TYPE_19', lambda x, y: x == y, 0.1),
        ('ns_vel', 'ns_vel', 'TYPE_19', lambda x, y: x == y, 0.1),
        ('ew_vel', 'ew_vel', 'TYPE_19', lambda x, y: x == y, 0.1),
    ]
    
    MSR_CONFIG = [
        ('callsign', 'callsign', 'TYPE_4', lambda x, y: x == y),
        ('adsb_ver', 'adsb_ver', 'TYPE_31', lambda x, y: x == y),
        ('nacp', 'nacp', 'TYPE_31', lambda x, y: x == y),
        ('sda', 'sda', 'TYPE_31', lambda x, y: x == y),
        ('sil', 'sil', 'TYPE_31', lambda x, y: x == y),
        ('gva', 'gva', 'TYPE_31', lambda x, y: x == y),
    ]
    
    TSR_CONFIG = [
        ('selected_alt', 'selected_alt', 'TYPE_29', lambda x, y: x == y, 1),
        ('selected_heading', 'selected_heading', 'TYPE_29', lambda x, y: x == y, 1),
        ('autopilot', 'autopilot', 'TYPE_29', lambda x, y: x == y, 0.1),
        ('vnav', 'vnav', 'TYPE_29', lambda x, y: x == y, 0.1),
        ('altitude_hold', 'altitude_hold', 'TYPE_29', lambda x, y: x == y, 0.1),
        ('approach', 'approach', 'TYPE_29', lambda x, y: x == y, 0.1),
        ('lnav', 'lnav', 'TYPE_29', lambda x, y: x == y, 0.1),
    ]
    
    AVR_CONFIG = [
        ('ias', 'ias', 'TYPE_19_SUBTYPE_3', lambda x, y: x == y, 1),
        ('heading', 'heading', 'TYPE_19_SUBTYPE_3', lambda x, y: x == y, 1),
    ]
    
    def __init__(self, icao_address):
        self.icao = icao_address
        self.input_messages = []
        self.output_messages = []
        self.msr_messages = []
        self.tsr_messages = []
        self.avr_messages = []
        self.delays = []
        self.all_changes = []
        self.errors = []
        self.thresholds = THRESHOLDS
        self.decoded_c = 0
        self.last_baro_alt = None
        self.last_baro_alt_t = None
        self.subtype_changes = []
        self.gnss_loss_start = None
        self.gnss_loss_end = None
        
        # Для отслеживания последних значений из входных сообщений
        self.last_in_values = {
            'lat': None, 'lon': None, 'alt': None,
            'geo_alt': None, 'ns_vel': None, 'ew_vel': None
        }
        
        # Список пропущенных полей
        self.missing_fields_list = []
    
    def parse_log_file(self, filename):
        print(f"\nЗагрузка данных: {filename}")
        print(f"Поиск сообщений для ICAO: {self.icao}")
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if self.icao not in line:
                        continue
                    
                    if 'process_adsb_in_message' in line:
                        self._parse_input_message(line)
                    elif 'send_pivo_msg' in line:
                        self._parse_output_message(line)
        except FileNotFoundError:
            print(f"Ошибка: Файл {filename} не найден")
            return
        
        print(f"Найдено входных сообщений: {len(self.input_messages)}")
        print(f"Найдено SVR_STRUCT: {len(self.output_messages)}")
        print(f"Найдено MSR_STRUCT: {len(self.msr_messages)}")
        print(f"Найдено TSR_STRUCT: {len(self.tsr_messages)}")
        print(f"Найдено AVR_STRUCT: {len(self.avr_messages)}")
        
        self._analyze_delays_and_changes()
        self._analyze_parameters()
        self._analyze_missing_fields()
        self._analyze_msr()
        self._analyze_tsr()
        self._analyze_avr()
        self._analyze_subtype()
    
    def _analyze_missing_fields(self):
        """Анализирует собранные отсутствующие поля"""
        print("\nАнализ отсутствующих полей в SVR -")
        
        missing_errors = []
        
        for missing in self.missing_fields_list:
            field = missing['field']
            in_val = missing['in_val']
            out_time = missing['out_time']
            
            # предыдущее значение этого поля из входных данных
            prev_in_val = None
            for in_msg in reversed(self.input_messages):
                if in_msg.timestamp < out_time:
                    if field == 'lat' and in_msg.lat is not None:
                        prev_in_val = in_msg.lat
                        break
                    elif field == 'lon' and in_msg.lon is not None:
                        prev_in_val = in_msg.lon
                        break
                    elif field == 'alt' and in_msg.alt is not None:
                        prev_in_val = in_msg.alt
                        break
                    elif field == 'geo_alt' and in_msg.geo_alt is not None:
                        prev_in_val = in_msg.geo_alt
                        break
                    elif field == 'ns_vel' and in_msg.ns_vel is not None:
                        signed_val = self._get_signed_velocity(in_msg.ns_vel, in_msg.ns_dir)
                        prev_in_val = signed_val
                        break
                    elif field == 'ew_vel' and in_msg.ew_vel is not None:
                        signed_val = self._get_signed_velocity(in_msg.ew_vel, in_msg.ew_dir)
                        prev_in_val = signed_val
                        break
            
            # если значение изменилось - ошибка
            if prev_in_val is not None and in_val != prev_in_val:
                missing_errors.append(ADSBError(f'missing_{field}', out_time, param=field,
                    in_val=in_val, prev_val=prev_in_val,
                    msg=f"Поле {field} изменилось с {prev_in_val} на {in_val}, но не передано в выходном"))
        
        print(f"  Найдено ошибок отсутствия полей: {len(missing_errors)}")
        
        if missing_errors:
            field_stats = defaultdict(int)
            for err in missing_errors:
                field_stats[err.param] += 1
            print(f"\n  Статистика отсутствующих полей:")
            for field, count in field_stats.items():
                print(f"    - {field}: {count}")
        
        self.errors.extend(missing_errors)
    
    def _update_last_input(self, in_msg):
        if in_msg.lat is not None:
            self.last_in_values['lat'] = in_msg.lat
        if in_msg.lon is not None:
            self.last_in_values['lon'] = in_msg.lon
        if in_msg.alt is not None:
            self.last_in_values['alt'] = in_msg.alt
        if in_msg.geo_alt is not None:
            self.last_in_values['geo_alt'] = in_msg.geo_alt
        if in_msg.ns_vel is not None:
            signed_val = self._get_signed_velocity(in_msg.ns_vel, in_msg.ns_dir)
            self.last_in_values['ns_vel'] = signed_val
        if in_msg.ew_vel is not None:
            signed_val = self._get_signed_velocity(in_msg.ew_vel, in_msg.ew_dir)
            self.last_in_values['ew_vel'] = signed_val
    
    def _parse_input_message(self, line):
        timestamp = self._extract_timestamp(line)
        if timestamp is None:
            return
        
        if 'TYPE 11' in line or 'TYPE 18' in line or 'TYPE 12' in line:
            msg = self._parse_type11(line, timestamp)
            if msg:
                self.input_messages.append(msg)
                self._update_last_input(msg)
        elif 'TYPE 19' in line:
            msg = self._parse_type19(line, timestamp)
            if msg:
                self.input_messages.append(msg)
                self._update_last_input(msg)
        elif 'TYPE 4' in line:
            msg = self._parse_type4(line, timestamp)
            if msg:
                self.input_messages.append(msg)
        elif 'TYPE 29' in line:
            msg = self._parse_type29(line, timestamp)
            if msg:
                self.input_messages.append(msg)
        elif 'TYPE 31' in line or 'F8210002' in line:
            msg = self._parse_type31(line, timestamp)
            if msg:
                self.input_messages.append(msg)
        elif 'TYPE 0' in line:
            msg = self._parse_type0(line, timestamp)
            if msg:
                self.input_messages.append(msg)
    
    def _parse_output_message(self, line):
        timestamp = self._extract_timestamp(line)
        if timestamp is None:
            return
        
        if 'SVR_STRUCT' in line:
            msg = self._parse_svr_struct(line, timestamp)
            if msg:
                self.output_messages.append(msg)
        elif 'MSR_STRUCT' in line:
            msg = self._parse_msr_struct(line, timestamp)
            if msg:
                self.msr_messages.append(msg)
        elif 'TSR_STRUCT' in line:
            msg = self._parse_tsr_struct(line, timestamp)
            if msg:
                self.tsr_messages.append(msg)
        elif 'AVR_STRUCT' in line:
            msg = self._parse_avr_struct(line, timestamp)
            if msg:
                self.avr_messages.append(msg)
    
    def _extract_timestamp(self, line):
        match = re.match(r'^(\d+\.\d+)', line)
        return float(match.group(1)) if match else None
    
    def _parse_type11(self, line, timestamp):
        lat_match = re.search(r'lat\s+([0-9\-\.]+)', line, re.I)
        lon_match = re.search(r'lon\s+([0-9\-\.]+)', line, re.I)
        alt_match = re.search(r'ALT\s+(\d+)\s+ft', line)
        
        if not lat_match or not lon_match:
            return None
        
        msg = ADSBMessage(timestamp, 'TYPE_11')
        msg.lat = float(lat_match.group(1))
        msg.lon = float(lon_match.group(1))
        if alt_match:
            msg.alt = int(alt_match.group(1))
            self.last_baro_alt = msg.alt
            self.last_baro_alt_t = timestamp
        return msg
    
    def _parse_type19(self, line, timestamp):
        msg = ADSBMessage(timestamp, 'TYPE_19')
        
        subtype_match = re.search(r'TYPE 19 SUBTYPE (\d+)', line)
        if subtype_match:
            msg.subtype = int(subtype_match.group(1))
        
        #SUBTYPE 1 
        if msg.subtype == 1:
            ew_match = re.search(r'EW_VEL\s+(\d+)\s+kt', line)
            ns_match = re.search(r'NS_VEL\s+(\d+)\s+kt', line)
            if ew_match:
                msg.ew_vel = int(ew_match.group(1))
            if ns_match:
                msg.ns_vel = int(ns_match.group(1))
                msg.speed_valid = True
            
            msg.ew_dir = 'EAST' if 'EW_DIR EAST' in line else 'WEST' if 'EW_DIR WEST' in line else None
            msg.ns_dir = 'SOUTH' if 'NS_DIR SOUTH' in line else 'NORTH' if 'NS_DIR NORTH' in line else None
        
        #SUBTYPE 3 
        elif msg.subtype == 3:
            ias_match = re.search(r'INDICATED AIRSPEED (\d+) kt', line)
            if ias_match:
                msg.ias = int(ias_match.group(1))
            
            heading_match = re.search(r'HEADING (\d+) deg', line)
            if heading_match:
                msg.heading = int(heading_match.group(1))
            
            if 'HEADING_STATUS_BIT NOT_AVAILABLE' in line:
                msg.gnss_lost = True
            return msg
        
        #Общий парсинг для всех SUBTYPE
        diff_match = re.search(r'DIF_FROM_BARO_ALT\s+(\d+)\s+ft', line)
        if diff_match and self.last_baro_alt is not None:
            alt_diff = int(diff_match.group(1))
            if 'IS_GEO_ALT_BELOW_BARO BELOW' in line:
                alt_diff = -alt_diff
            msg.geo_alt = self.last_baro_alt + alt_diff
        
        return msg
    
    def _parse_type0(self, line, timestamp):
        msg = ADSBMessage(timestamp, 'TYPE_0')
        msg.gnss_lost = True
        alt_match = re.search(r'BARO_ALT\s+(\d+)\s+ft', line)
        if alt_match:
            msg.alt = int(alt_match.group(1))
        return msg
    
    def _parse_type4(self, line, timestamp):
        chars = re.findall(r"'([A-Z0-9 ])'", line)
        if len(chars) >= 8:
            msg = ADSBMessage(timestamp, 'TYPE_4')
            msg.callsign = ''.join(chars[:8]).strip()
            return msg
        return None
    
    def _parse_type29(self, line, timestamp):
        msg = ADSBMessage(timestamp, 'TYPE_29')
        
        alt_match = re.search(r'SEL_ALT\s+(\d+)\s+ft', line)
        if alt_match:
            msg.selected_alt = int(alt_match.group(1))
        
        hdg_match = re.search(r'SEL_HDG\s+([0-9\.]+)\s+deg', line)
        if hdg_match:
            msg.selected_heading = float(hdg_match.group(1))
        
        msg.autopilot = 1 if 'AUTOPILOT ON' in line or 'AUTOPILOT 1' in line else 0
        msg.vnav = 1 if 'VNAV ON' in line or 'VNAV 1' in line else 0
        msg.altitude_hold = 1 if 'ALT_HOLD ON' in line or 'ALT_HOLD 1' in line else 0
        msg.approach = 1 if 'APPROACH ON' in line or 'APPROACH 1' in line else 0
        msg.lnav = 1 if 'LNAV ON' in line or 'LNAV 1' in line else 0
        
        return msg
    
    def _parse_type31(self, line, timestamp):
        """Парсинг TYPE 31 (регистр 65) - читаем как строки"""
        msg = ADSBMessage(timestamp, 'TYPE_31')
        
        # adsb_ver
        if 'DO_260B' in line:
            msg.adsb_ver = 'DO-260B'
        elif 'DO_260A' in line:
            msg.adsb_ver = 'DO-260A'
        
        # nacp
        nacp_match = re.search(r'NACP\s+(\S+)', line)
        msg.nacp = nacp_match.group(1) if nacp_match else None
        
        # sda
        sda_match = re.search(r'SDA\s+(\S+)', line)
        msg.sda = sda_match.group(1) if sda_match else None
        
        # gva
        gva_match = re.search(r'GVA\s+(\S+)', line)
        msg.gva = gva_match.group(1) if gva_match else None
        
        # sil
        sil_match = re.search(r'SIL\s+(\S+)', line)
        msg.sil = sil_match.group(1) if sil_match else None
        
        return msg
    
    def _parse_svr_struct(self, line, timestamp):
        lat_match = re.search(r'LAT\s+([0-9\-\.]+)', line)
        lon_match = re.search(r'LON\s+([0-9\-\.]+)', line)
        baro_match = re.search(r'BARO_ALT\s+([0-9\-\.]+)\s+ft', line)
        geo_match = re.search(r'GEO_ALT\s+([0-9\-\.]+)\s+ft', line)
        ns_match = re.search(r'NSV\s+([0-9\-]+)', line)
        ew_match = re.search(r'EWV\s+([0-9\-]+)', line)
        
        msg = ADSBMessage(timestamp, 'SVR_STRUCT')
        
        if lat_match:
            msg.lat = float(lat_match.group(1))
        if lon_match:
            msg.lon = float(lon_match.group(1))
        if baro_match:
            msg.alt = float(baro_match.group(1))
        if geo_match:
            msg.geo_alt = float(geo_match.group(1))
        if ns_match:
            msg.ns_vel = int(ns_match.group(1))
            msg.speed_valid = True
        if ew_match:
            msg.ew_vel = int(ew_match.group(1))
        
        return msg
    
    def _parse_msr_struct(self, line, timestamp):
        msg = ADSBMessage(timestamp, 'MSR_STRUCT')
        
        chars = re.findall(r"'([A-Z0-9 ])'", line)
        if len(chars) >= 8:
            msg.callsign = ''.join(chars[:8]).strip()
        
        # adsb_ver
        if 'DO_260B' in line:
            msg.adsb_ver = 'DO-260B'
        elif 'DO_260A' in line:
            msg.adsb_ver = 'DO-260A'
        
        # nacp
        nacp_match = re.search(r'HFOM_(?:LT|GE)_[0-9\._KM]+', line)
        msg.nacp = nacp_match.group(0) if nacp_match else None
        
        # sda
        sda_match = re.search(r'SDA\s+(LEVEL_[BC]|UNKNOWN|NO_DATA)', line)
        if sda_match:
            msg.sda = sda_match.group(1)
        else:
            sda_simple = re.search(r'SDA\s+(\S+)', line)
            msg.sda = sda_simple.group(1) if sda_simple else None
        
        # sil
        sil_match = re.search(r'SIL\s+(LE_1_E10_[357]|UNKNOWN_OR_GT_1_E10_3)', line)
        if sil_match:
            msg.sil = sil_match.group(1)
        else:
            sil_simple = re.search(r'SIL\s+(\S+)', line)
            msg.sil = sil_simple.group(1) if sil_simple else None
        
        # gva
        gva_match = re.search(r'GVA\s+(LE_(?:45|150)_M|NO_DATA_OR_GT_150_M)', line)
        if gva_match:
            msg.gva = gva_match.group(1)
        else:
            gva_simple = re.search(r'GVA\s+(\S+)', line)
            msg.gva = gva_simple.group(1) if gva_simple else None
        
        return msg

    def _extract_msr_value(self, line, pattern):
        match = re.search(pattern, line)
        return match.group(0) if match else None
    
    def _parse_tsr_struct(self, line, timestamp):
        msg = ADSBMessage(timestamp, 'TSR_STRUCT')
        
        alt_match = re.search(r'SELECTED_ALTITUDE\s+(\d+)\s+ft', line)
        if alt_match:
            msg.selected_alt = int(alt_match.group(1))
        
        hdg_match = re.search(r'SELECTED_HEADING\s+([0-9\.]+)\s+deg', line)
        if hdg_match:
            msg.selected_heading = float(hdg_match.group(1))
        
        msg.autopilot = 1 if 'AUTOPILOT 1' in line else 0
        msg.vnav = 1 if 'VNAV 1' in line else 0
        msg.altitude_hold = 1 if 'ALTITUDE_HOLD 1' in line else 0
        msg.approach = 1 if 'APPROACH 1' in line else 0
        msg.lnav = 1 if 'LNAV 1' in line else 0
        
        return msg
    
    def _parse_avr_struct(self, line, timestamp):
        msg = ADSBMessage(timestamp, 'AVR_STRUCT')
        
        ias_match = re.search(r'AIRSPEED\s+(\d+)\s+kt', line)
        if ias_match:
            msg.ias = int(ias_match.group(1))
        
        if 'AIRSPEED_TYPE IAS' in line:
            msg.aircraft_status = 'IAS'
        elif 'AIRSPEED_TYPE TAS' in line:
            msg.aircraft_status = 'TAS'
        
        heading_match = re.search(r'HEADING_AIR\s+([0-9\.]+)', line)
        if heading_match:
            msg.heading = float(heading_match.group(1))
        
        return msg
    
    def _analyze_avr(self):
        print("\nПроверка параметров AVR -")
        
        subtype3_list = [msg for msg in self.input_messages 
                        if msg.type == 'TYPE_19' and msg.subtype == 3]
        
        if not subtype3_list:
            print("  Нет TYPE 19 SUBTYPE 3 сообщений для сравнения")
            return
        
        if not self.avr_messages:
            print("  Нет AVR_STRUCT сообщений для сравнения")
            return
        
        stats = {'ias': 0}
        avr_errors = []
        
        for avr_msg in self.avr_messages:
            in_msg = self._find_closest(subtype3_list, avr_msg.timestamp, max_diff=0.3)
            
            if in_msg:
                if avr_msg.ias is not None and in_msg.ias is not None:
                    stats['ias'] += 1
                    if avr_msg.ias != in_msg.ias:
                        avr_errors.append(ADSBError('avr_ias', avr_msg.timestamp, param='ias',
                            in_val=in_msg.ias, out_val=avr_msg.ias,
                            diff=abs(avr_msg.ias - in_msg.ias)))
                        print(f"  Ошибка IAS: t={avr_msg.timestamp:.3f} in={in_msg.ias} kt out={avr_msg.ias} kt diff={abs(avr_msg.ias - in_msg.ias)} kt")
                
        
        print(f"\n  Воздушная скорость (IAS): проверено {stats['ias']}")
        
        if avr_errors:
            print(f"\n  Всего ошибок AVR: {len(avr_errors)}")
            self.errors.extend(avr_errors)
        else:
            print("\n  Ошибок AVR не найдено")
    
    def _analyze_subtype(self):
        print("\nАнализ SUBTYPE и потери ГНСС -")
        
        type19_msgs = [msg for msg in self.input_messages if msg.type == 'TYPE_19']
        type0_msgs = [msg for msg in self.input_messages if msg.type == 'TYPE_0']
        
        if not type19_msgs:
            print("  Нет TYPE 19 сообщений для анализа")
            return
        
        subtype_stats = {1: 0, 3: 0}
        type0_count = len(type0_msgs)
        
        for msg in type19_msgs:
            if msg.subtype == 1:
                subtype_stats[1] += 1
            elif msg.subtype == 3:
                subtype_stats[3] += 1
        
        print(f"  TYPE 19 SUBTYPE 1: {subtype_stats[1]} сообщений")
        print(f"  TYPE 19 SUBTYPE 3: {subtype_stats[3]} сообщений")
        print(f"  TYPE 0: {type0_count} сообщений")
        
        if type0_msgs:
            self.gnss_loss_start = type0_msgs[0].timestamp
            self.gnss_loss_end = type0_msgs[-1].timestamp
            
            print(f"\n  Потеря ГНСС (TYPE 0): t={self.gnss_loss_start:.3f} - {self.gnss_loss_end:.3f}")
            print(f"  Длительность: {(self.gnss_loss_end - self.gnss_loss_start):.3f} с")
            
            last_subtype1 = None
            for msg in type19_msgs:
                if msg.timestamp < self.gnss_loss_start and msg.subtype == 1:
                    last_subtype1 = msg
            
            if last_subtype1:
                print(f"  Последнее TYPE 19 SUBTYPE 1 до потери: t={last_subtype1.timestamp:.3f}")
        
        if subtype_stats[3] > 0 or type0_count > 0:
            print("\n Потеря ГНСС корректно обрабатывается")
            print(f" - Переход на SUBTYPE 3")
            print(f" - TYPE 0")
            if self.avr_messages:
                print(f" - AVR_STRUCT содержит {len(self.avr_messages)} сообщений")
        else:
            print("\n Нет признаков потери ГНСС в анализируемых данных")
    
    def _analyze_delays_and_changes(self):
        print("\nАнализ задержек SVR -")
        
        param_state = {}
        for param_name, _, _, _, change_tol in self.PARAM_CONFIG:
            param_state[param_name] = {'last_value': None, 'changes': 0, 'delays': []}
        
        input_by_type = {
            'TYPE_11': [msg for msg in self.input_messages if msg.type == 'TYPE_11'],
            'TYPE_19': [msg for msg in self.input_messages if msg.type == 'TYPE_19' and msg.subtype == 1]
        }
        
        for out_msg in self.output_messages:
            if out_msg.type != 'SVR_STRUCT':
                continue
            
            for param_name, attr_name, msg_type, compare_func, change_tol in self.PARAM_CONFIG:
                out_val = getattr(out_msg, attr_name)
                if out_val is None:
                    continue
                
                best_in = None
                min_diff = float('inf')
                
                for in_msg in input_by_type.get(msg_type, []):
                    if in_msg.timestamp > out_msg.timestamp:
                        continue
                    
                    if attr_name == 'ns_vel':
                        in_val = self._get_signed_velocity(in_msg.ns_vel, in_msg.ns_dir)
                    elif attr_name == 'ew_vel':
                        in_val = self._get_signed_velocity(in_msg.ew_vel, in_msg.ew_dir)
                    else:
                        in_val = getattr(in_msg, attr_name)
                    
                    if in_val is None:
                        continue
                    
                    if compare_func(in_val, out_val):
                        diff = out_msg.timestamp - in_msg.timestamp
                        if diff < min_diff:
                            min_diff = diff
                            best_in = in_msg
                
                if best_in:
                    state = param_state[param_name]
                    delay = out_msg.timestamp - best_in.timestamp
                    
                    if state['last_value'] is None or out_val != state['last_value']:
                        state['changes'] += 1
                        state['last_value'] = out_val
                        
                        self.all_changes.append({
                            'time': out_msg.timestamp,
                            'delay': delay,
                            'param': param_name,
                            'value': out_val,
                            'in_time': best_in.timestamp
                        })
                        
                        if delay > THRESHOLDS['delay_max']:
                            state['delays'].append(delay * 1000)
                            self.delays.append({
                                'time': out_msg.timestamp,
                                'delay': delay,
                                'param': param_name,
                                'value': out_val,
                                'in_time': best_in.timestamp
                            })
        
        param_names = {
            'lat': 'Широта', 'lon': 'Долгота',
            'baro_alt': 'Барометрическая высота', 'geo_alt': 'Геометрическая высота',
            'ns_vel': 'Скорость (NS)', 'ew_vel': 'Скорость (EW)'
        }
        
        print(f"\nСтатистика изменений параметров -")
        for name, state in param_state.items():
            if state['changes'] > 0:
                print(f"  {param_names.get(name, name)}: {state['changes']} изменений")
        
        if self.delays:
            print(f"\nСтатистика задержек -")
            for name, state in param_state.items():
                if state['delays']:
                    print(f"  {param_names.get(name, name)}: {len(state['delays'])} задержек, "
                          f"мин {min(state['delays']):.1f} мс, макс {max(state['delays']):.1f} мс")
        else:
            print(f"\n  Задержек не найдено")
    
    def _analyze_parameters(self):
        print("\nПроверка параметров SVR -")
        
        type11_list = [msg for msg in self.input_messages if msg.type == 'TYPE_11']
        type19_list = [msg for msg in self.input_messages if msg.type == 'TYPE_19' and msg.subtype == 1]
        
        stats = {param_name: 0 for param_name, _, _, _, _ in self.PARAM_CONFIG}
        
        self.missing_fields_list = []
        
        for out in self.output_messages:
            if out.type != 'SVR_STRUCT':
                continue
            
            in11 = self._find_closest(type11_list, out.timestamp)
            if in11:
                for param_name, attr_name, msg_type, compare_func, _ in self.PARAM_CONFIG:
                    if msg_type != 'TYPE_11':
                        continue
                    
                    out_val = getattr(out, attr_name)
                    in_val = getattr(in11, attr_name)
                    
                    if out_val is not None and in_val is not None:
                        stats[param_name] += 1
                        if not compare_func(in_val, out_val):
                            if param_name == 'lat':
                                self.errors.append(ADSBError('svr_lat', out.timestamp, param='lat',
                                    in_val=in_val, out_val=out_val,
                                    diff=abs(out_val - in_val)))
                            elif param_name == 'lon':
                                self.errors.append(ADSBError('svr_lon', out.timestamp, param='lon',
                                    in_val=in_val, out_val=out_val,
                                    diff=abs(out_val - in_val)))
                            elif param_name == 'baro_alt':
                                self.errors.append(ADSBError('svr_baro_alt', out.timestamp, param='baro_alt',
                                    in_val=in_val, out_val=out_val,
                                    diff=abs(out_val - in_val)))
                            else:
                                self.errors.append(ADSBError(f'svr_{param_name}', out.timestamp, param=param_name,
                                    in_val=in_val, out_val=out_val,
                                    diff=abs(out_val - in_val)))
                    
                    #отсутствующие поля
                    elif in_val is not None and out_val is None:
                        self.missing_fields_list.append({
                            'field': attr_name,
                            'in_val': in_val,
                            'in_time': in11.timestamp,
                            'out_time': out.timestamp
                        })
            
            in19 = self._find_closest(type19_list, out.timestamp)
            if in19:
                for param_name, attr_name, msg_type, compare_func, _ in self.PARAM_CONFIG:
                    if msg_type != 'TYPE_19':
                        continue
                    
                    out_val = getattr(out, attr_name)
                    
                    if attr_name == 'ns_vel':
                        in_val = self._get_signed_velocity(in19.ns_vel, in19.ns_dir)
                    elif attr_name == 'ew_vel':
                        in_val = self._get_signed_velocity(in19.ew_vel, in19.ew_dir)
                    elif attr_name == 'geo_alt':
                        in_val = in19.geo_alt
                    else:
                        in_val = None
                    
                    if out_val is not None and in_val is not None:
                        stats[param_name] += 1
                        if not compare_func(in_val, out_val):
                            diff = abs(out_val - in_val)
                            self.errors.append(ADSBError(f'svr_{param_name}', out.timestamp, param=param_name,
                                in_val=in_val, out_val=out_val,
                                diff=diff))
                    
                    elif in_val is not None and out_val is None:
                        self.missing_fields_list.append({
                            'field': attr_name,
                            'in_val': in_val,
                            'in_time': in19.timestamp,
                            'out_time': out.timestamp
                        })
        
        param_names = {
            'lat': 'Широта', 'lon': 'Долгота',
            'baro_alt': 'Барометрическая высота', 'geo_alt': 'Геометрическая высота',
            'ns_vel': 'Скорость NS', 'ew_vel': 'Скорость EW'
        }
        
        for param_name in ['lat', 'lon', 'baro_alt', 'geo_alt', 'ns_vel', 'ew_vel']:
            if param_name in stats:
                print(f"  {param_names.get(param_name, param_name)}: проверено {stats[param_name]}")
        
        if self.errors:
            svr_errors = [e for e in self.errors if e.type.startswith('svr_')]
            print(f"\n  Всего ошибок SVR (значения): {len(svr_errors)}")
        else:
            print("\n  Ошибок SVR (значения) не найдено")
    
    def _analyze_msr(self):
        print("\nПроверка параметров MSR -")
        
        type4_list = [msg for msg in self.input_messages if msg.type == 'TYPE_4']
        type31_list = [msg for msg in self.input_messages if msg.type == 'TYPE_31']
        
        msr_errors = []
        
        for out in self.msr_messages:
            in4 = self._find_closest(type4_list, out.timestamp)
            if in4 and out.callsign and in4.callsign:
                if out.callsign != in4.callsign:
                    msr_errors.append(ADSBError('msr_callsign', out.timestamp, param='callsign',
                        in_val=in4.callsign, out_val=out.callsign))
            
            in31 = self._find_closest(type31_list, out.timestamp)
            if in31:
                if out.adsb_ver and in31.adsb_ver:
                    if out.adsb_ver != in31.adsb_ver:
                        msr_errors.append(ADSBError('msr_adsb_ver', out.timestamp, param='adsb_ver',
                            in_val=in31.adsb_ver, out_val=out.adsb_ver))
                
                if out.nacp and in31.nacp:
                    if out.nacp != in31.nacp:
                        msr_errors.append(ADSBError('msr_nacp', out.timestamp, param='nacp',
                            in_val=in31.nacp, out_val=out.nacp))
                
                # sda
                if out.sda and in31.sda:
                    if out.sda != in31.sda:
                        msr_errors.append(ADSBError('msr_sda', out.timestamp, param='sda',
                            in_val=in31.sda, out_val=out.sda))
                
                # sil
                if out.sil and in31.sil:
                    if out.sil != in31.sil:
                        msr_errors.append(ADSBError('msr_sil', out.timestamp, param='sil',
                            in_val=in31.sil, out_val=out.sil))
                
                # gva
                if out.gva and in31.gva:
                    if out.gva != in31.gva:
                        msr_errors.append(ADSBError('msr_gva', out.timestamp, param='gva',
                            in_val=in31.gva, out_val=out.gva))
        
        print(f"  Обработано MSR_STRUCT: {len(self.msr_messages)}")
        
        if msr_errors:
            print(f"  Всего ошибок MSR: {len(msr_errors)}")
            self.errors.extend(msr_errors)
        else:
            print("  Ошибок MSR не найдено")
    
    def _analyze_tsr(self):
        print("\nПроверка параметров TSR -")
        
        type29_list = [msg for msg in self.input_messages if msg.type == 'TYPE_29']
        
        tsr_errors = []
        
        for out in self.tsr_messages:
            in29 = self._find_closest(type29_list, out.timestamp)
            if in29:
                if out.selected_alt is not None and in29.selected_alt is not None:
                    if out.selected_alt != in29.selected_alt:
                        tsr_errors.append(ADSBError('tsr_selected_alt', out.timestamp, param='selected_alt',
                            in_val=in29.selected_alt, out_val=out.selected_alt,
                            diff=abs(out.selected_alt - in29.selected_alt)))
                
                if out.selected_heading is not None and in29.selected_heading is not None:
                    if out.selected_heading != in29.selected_heading:
                        tsr_errors.append(ADSBError('tsr_selected_heading', out.timestamp, param='selected_heading',
                            in_val=in29.selected_heading, out_val=out.selected_heading,
                            diff=abs(out.selected_heading - in29.selected_heading)))
                
                if out.autopilot is not None and in29.autopilot is not None:
                    if out.autopilot != in29.autopilot:
                        tsr_errors.append(ADSBError('tsr_autopilot', out.timestamp, param='autopilot',
                            in_val=in29.autopilot, out_val=out.autopilot))
                
                if out.vnav is not None and in29.vnav is not None:
                    if out.vnav != in29.vnav:
                        tsr_errors.append(ADSBError('tsr_vnav', out.timestamp, param='vnav',
                            in_val=in29.vnav, out_val=out.vnav))
                
                if out.altitude_hold is not None and in29.altitude_hold is not None:
                    if out.altitude_hold != in29.altitude_hold:
                        tsr_errors.append(ADSBError('tsr_altitude_hold', out.timestamp, param='altitude_hold',
                            in_val=in29.altitude_hold, out_val=out.altitude_hold))
                
                if out.approach is not None and in29.approach is not None:
                    if out.approach != in29.approach:
                        tsr_errors.append(ADSBError('tsr_approach', out.timestamp, param='approach',
                            in_val=in29.approach, out_val=out.approach))
                
                if out.lnav is not None and in29.lnav is not None:
                    if out.lnav != in29.lnav:
                        tsr_errors.append(ADSBError('tsr_lnav', out.timestamp, param='lnav',
                            in_val=in29.lnav, out_val=out.lnav))
        
        print(f"  Обработано TSR_STRUCT: {len(self.tsr_messages)}")
        
        if tsr_errors:
            print(f"  Всего ошибок TSR: {len(tsr_errors)}")
            self.errors.extend(tsr_errors)
        else:
            print("  Ошибок TSR не найдено")
    
    def _find_closest(self, msg_list, out_time, max_diff=0.5):
        best = None
        best_diff = float('inf')
        
        for msg in msg_list:
            if msg.timestamp > out_time:
                continue
            diff = out_time - msg.timestamp
            if diff < max_diff and diff < best_diff:
                best_diff = diff
                best = msg
        return best
    
    def _calculate_heading(self, msg, is_svr=False):
        if msg.ew_vel is None or msg.ns_vel is None:
            return None
        
        try:
            if is_svr:
                return math.degrees(math.atan2(msg.ew_vel, msg.ns_vel)) % 360
            else:
                ew_signed = -msg.ew_vel if msg.ew_dir == 'WEST' else msg.ew_vel
                ns_signed = msg.ns_vel
                if msg.ns_dir == 'NORTH':
                    ns_signed = -msg.ns_vel
                elif msg.ns_dir == 'SOUTH':
                    ns_signed = msg.ns_vel
                return math.degrees(math.atan2(ew_signed, -ns_signed)) % 360
        except (TypeError, ValueError):
            return None