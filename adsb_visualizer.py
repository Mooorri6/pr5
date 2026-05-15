import matplotlib.pyplot as plt
from datetime import datetime
import os
from collections import defaultdict

class ADSBVisualizer:
    
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.icao = analyzer.icao
        self.thresholds = analyzer.thresholds
        
        self.base_dir = f"errors_{self.icao}"
        self._create_dirs()
    
    def _create_dirs(self):
        """Создание структуры папок по типам донесений"""
        self.dirs = {
            'SVR': os.path.join(self.base_dir, 'SVR'),
            'MSR': os.path.join(self.base_dir, 'MSR'),
            'TSR': os.path.join(self.base_dir, 'TSR'),
            'AVR': os.path.join(self.base_dir, 'AVR'),
            'DUPLICATE': os.path.join(self.base_dir, 'DUPLICATE'),
        }
        for d in self.dirs.values():
            if not os.path.exists(d):
                os.makedirs(d)
    
    def _get_report_type(self, error_type):
        """Определение типа донесения по типу ошибки"""
        if error_type.startswith('duplicate_'):
            return 'DUPLICATE' 
        elif error_type.startswith('svr_'):
            return 'SVR'
        elif error_type.startswith('msr_'):
            return 'MSR'
        elif error_type.startswith('tsr_'):
            return 'TSR'
        elif error_type.startswith('avr_'):
            return 'AVR'
        return 'OTHER'
    
    def plot_all(self):
        self.plot_parameters()
        self.plot_heading()
        self.plot_changes_by_param()
        self.plot_tsr()
        self._write_error_files()
    
    def plot_heading(self):
        in_data = self._collect_input_data()
        out_data = self._collect_output_data()
        
        if not in_data['hdg_times'] and not out_data['hdg_times']:
            print("Нет данных о курсе для построения графика")
            return
        
        plt.figure(figsize=(14, 8))
        
        if in_data['hdg_times']:
            plt.plot(in_data['hdg_times'], in_data['hdgs'], 'b.', 
                    markersize=4, label='TYPE_19 (входные)', alpha=0.7)
        
        if out_data['hdg_times']:
            plt.plot(out_data['hdg_times'], out_data['hdgs'], 'r.', 
                    markersize=4, label='SVR_STRUCT (выходные)', alpha=0.7)
        
        plt.xlabel('Время (с)')
        plt.ylabel('Курс (градусы)')
        plt.title(f'Курс - ICAO {self.icao}')
        plt.grid(True, alpha=0.3)
        plt.legend(loc='upper right', fontsize=10)
        
        if in_data['hdg_times']:
            text = (f'Измерений TYPE_19: {len(in_data["hdg_times"])}\n'
                   f'Измерений SVR_STRUCT: {len(out_data["hdg_times"])}')
            
            plt.text(0.02, 0.95, text, transform=plt.gca().transAxes, 
                    verticalalignment='top', bbox=dict(boxstyle='round', 
                    facecolor='wheat', alpha=0.5), fontsize=10)
        
        plt.tight_layout()
        filename = f'heading_{self.icao}.png'
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"График курса сохранен: {filename}")
    
    def plot_changes_by_param(self):
        if not self.analyzer.all_changes:
            print("Нет данных об изменениях для построения графиков")
            return
    
        changes_by_param = {}
        for d in self.analyzer.all_changes:
            param = d['param']
            if param not in changes_by_param:
                changes_by_param[param] = []
            changes_by_param[param].append(d)
        
        colors = {
            'lat': 'blue',
            'lon': 'green',
            'baro_alt': 'orange',
            'geo_alt': 'brown',
            'ns_vel': 'red',
            'ew_vel': 'purple'
        }
        
        param_names = {
            'lat': 'Широта',
            'lon': 'Долгота',
            'baro_alt': 'Барометрическая высота',
            'geo_alt': 'Геометрическая высота',
            'ns_vel': 'Скорость (север-юг)',
            'ew_vel': 'Скорость (восток-запад)'
        }
        
        for param, changes in changes_by_param.items():
            if not changes:
                continue
            
            plt.figure(figsize=(14, 8))
            
            times = [d['time'] for d in changes]
            delays_ms = [d['delay'] * 1000 for d in changes]
            color = colors.get(param, 'gray')
            
            plt.plot(times, delays_ms, 'o-', color=color, linewidth=1, markersize=4, alpha=0.7)
            plt.axhline(y=500, color='r', linestyle='--', linewidth=1, 
                       label='Предел 500 мс', alpha=0.7)
            
            plt.xlabel('Время (с)')
            plt.ylabel('Задержка (мс)')
            title = param_names.get(param, param)
            plt.title(f'{title} - ICAO {self.icao} (все изменения)')
            plt.grid(True, alpha=0.3)
            plt.legend(loc='upper right', fontsize=10)
            
            if delays_ms:
                text = (f'Всего изменений: {len(delays_ms)}\n')
                plt.text(0.02, 0.95, text, transform=plt.gca().transAxes, 
                        verticalalignment='top', bbox=dict(boxstyle='round', 
                        facecolor='wheat', alpha=0.5), fontsize=10)
            
            plt.tight_layout()
            filename = f'changes_{param}_{self.icao}.png'
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"График изменений для {title} сохранен: {filename}")
    
    def _collect_input_data(self):
        data = {
            'times': [], 'lats': [], 'lons': [],
            'alt_times': [], 'alts': [],
            'geo_times': [], 'geos': [],
            'hdg_times': [], 'hdgs': [],
            'ns_vel_times': [], 'ns_vels': [],
            'ew_vel_times': [], 'ew_vels': []
        }
        
        for msg in self.analyzer.input_messages:
            if msg.type == 'TYPE_11' and msg.lat is not None:
                if abs(msg.lat) > 0.0001 and abs(msg.lon) > 0.0001:
                    data['times'].append(msg.timestamp)
                    data['lats'].append(msg.lat)
                    data['lons'].append(msg.lon)
                    if msg.alt is not None:
                        data['alt_times'].append(msg.timestamp)
                        data['alts'].append(msg.alt)
            
            elif msg.type == 'TYPE_19':
                if msg.geo_alt is not None:
                    data['geo_times'].append(msg.timestamp)
                    data['geos'].append(msg.geo_alt)
                
                if msg.speed_valid:
                    heading = self.analyzer._calculate_heading(msg)
                    if heading is not None:
                        data['hdg_times'].append(msg.timestamp)
                        data['hdgs'].append(heading)
                    
                    if msg.ns_vel is not None:
                        ns_signed = msg.ns_vel
                        if msg.ns_dir == 'SOUTH':
                            ns_signed = -msg.ns_vel
                        elif msg.ns_dir == 'NORTH':
                            ns_signed = msg.ns_vel
                        data['ns_vel_times'].append(msg.timestamp)
                        data['ns_vels'].append(ns_signed)
                    
                    if msg.ew_vel is not None:
                        ew_signed = msg.ew_vel
                        if msg.ew_dir == 'WEST':
                            ew_signed = -msg.ew_vel
                        elif msg.ew_dir == 'EAST':
                            ew_signed = msg.ew_vel
                        data['ew_vel_times'].append(msg.timestamp)
                        data['ew_vels'].append(ew_signed)
        
        return data

    def _collect_output_data(self):
        data = {
            'times': [], 'lats': [], 'lons': [],
            'alt_times': [], 'alts': [],
            'geo_times': [], 'geos': [],
            'hdg_times': [], 'hdgs': [],
            'ns_vel_times': [], 'ns_vels': [],
            'ew_vel_times': [], 'ew_vels': []
        }
        
        for msg in self.analyzer.output_messages:
            if msg.type == 'SVR_STRUCT':
                if msg.lat is not None and abs(msg.lat) > 0.0001:
                    data['times'].append(msg.timestamp)
                    data['lats'].append(msg.lat)
                    data['lons'].append(msg.lon)
                
                if msg.alt is not None:
                    data['alt_times'].append(msg.timestamp)
                    data['alts'].append(msg.alt)
                
                if msg.geo_alt is not None:
                    data['geo_times'].append(msg.timestamp)
                    data['geos'].append(msg.geo_alt)
                
                if msg.speed_valid:
                    heading = self.analyzer._calculate_heading(msg, is_svr=True)
                    if heading is not None:
                        data['hdg_times'].append(msg.timestamp)
                        data['hdgs'].append(heading)
                    
                    if msg.ns_vel is not None:
                        data['ns_vel_times'].append(msg.timestamp)
                        data['ns_vels'].append(msg.ns_vel)
                    
                    if msg.ew_vel is not None:
                        data['ew_vel_times'].append(msg.timestamp)
                        data['ew_vels'].append(msg.ew_vel)
        
        return data

    def plot_parameters(self):
        if not self.analyzer.output_messages:
            print("Недостаточно данных для построения графиков")
            return
        
        in_data = self._collect_input_data()
        out_data = self._collect_output_data()
        
        if not in_data['times'] and not out_data['times']:
            print("Нет данных для отображения")
            return
        
        fig, axes = plt.subplots(3, 2, figsize=(16, 12))
        fig.suptitle(f'Параметры ICAO {self.icao}', fontsize=14)
        
        # Широта
        ax1 = axes[0, 0]
        if in_data['times']:
            ax1.plot(in_data['times'], in_data['lats'], 'b-', 
                    linewidth=1, label='TYPE_11/18', alpha=0.7)
        if out_data['times']:
            ax1.plot(out_data['times'], out_data['lats'], 'r.', 
                    markersize=3, label='SVR_STRUCT')
        self._setup_plot(ax1, 'Время (с)', 'Широта (градусы)', 'Широта')
        
        # Долгота
        ax2 = axes[0, 1]
        if in_data['times']:
            ax2.plot(in_data['times'], in_data['lons'], 'b-', 
                    linewidth=1, label='TYPE_11/18', alpha=0.7)
        if out_data['times']:
            ax2.plot(out_data['times'], out_data['lons'], 'r.', 
                    markersize=3, label='SVR_STRUCT')
        self._setup_plot(ax2, 'Время (с)', 'Долгота (градусы)', 'Долгота')
        
        # Баро высота
        ax3 = axes[1, 0]
        if in_data['alt_times'] or out_data['alt_times']:
            if in_data['alt_times']:
                ax3.plot(in_data['alt_times'], in_data['alts'], 'b.', 
                        markersize=2, label='TYPE_11 (BARO)', alpha=0.7)
            if out_data['alt_times']:
                ax3.plot(out_data['alt_times'], out_data['alts'], 'r.', 
                        markersize=3, label='SVR_STRUCT (BARO)')
            self._setup_plot(ax3, 'Время (с)', 'Высота (футы)', 'Барометрическая высота')
        else:
            ax3.text(0.5, 0.5, 'Нет данных', transform=ax3.transAxes, ha='center', va='center')
            ax3.set_title('Барометрическая высота')
        
        # Гео высота
        ax4 = axes[1, 1]
        if in_data['geo_times'] or out_data['geo_times']:
            if in_data['geo_times']:
                ax4.plot(in_data['geo_times'], in_data['geos'], 'b.', 
                        markersize=2, label='TYPE_19 (GEO)', alpha=0.7)
            if out_data['geo_times']:
                ax4.plot(out_data['geo_times'], out_data['geos'], 'r.', 
                        markersize=3, label='SVR_STRUCT (GEO)')
            self._setup_plot(ax4, 'Время (с)', 'Высота (футы)', 'Геометрическая высота')
        else:
            ax4.text(0.5, 0.5, 'Нет данных', transform=ax4.transAxes, ha='center', va='center')
            ax4.set_title('Геометрическая высота')
        
        # Скорость NS
        ax5 = axes[2, 0]
        if in_data['ns_vel_times'] or out_data['ns_vel_times']:
            if in_data['ns_vel_times']:
                ax5.plot(in_data['ns_vel_times'], in_data['ns_vels'], 'b.', 
                        markersize=2, label='TYPE_19 (NS)', alpha=0.7)
            if out_data['ns_vel_times']:
                ax5.plot(out_data['ns_vel_times'], out_data['ns_vels'], 'r.', 
                        markersize=3, label='SVR_STRUCT (NS)')
            self._setup_plot(ax5, 'Время (с)', 'Скорость (узлы)', 'Скорость North-South')
        else:
            ax5.text(0.5, 0.5, 'Нет данных', transform=ax5.transAxes, ha='center', va='center')
            ax5.set_title('Скорость North-South')
        
        # Скорость EW
        ax6 = axes[2, 1]
        if in_data['ew_vel_times'] or out_data['ew_vel_times']:
            if in_data['ew_vel_times']:
                ax6.plot(in_data['ew_vel_times'], in_data['ew_vels'], 'b.', 
                        markersize=2, label='TYPE_19 (EW)', alpha=0.7)
            if out_data['ew_vel_times']:
                ax6.plot(out_data['ew_vel_times'], out_data['ew_vels'], 'r.', 
                        markersize=3, label='SVR_STRUCT (EW)')
            self._setup_plot(ax6, 'Время (с)', 'Скорость (узлы)', 'Скорость East-West')
        else:
            ax6.text(0.5, 0.5, 'Нет данных', transform=ax6.transAxes, ha='center', va='center')
            ax6.set_title('Скорость East-West')
        
        plt.tight_layout()
        filename = f'param_{self.icao}.png'
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"График параметров сохранен: {filename}")

    def gen_report(self):
        filename = f'test_report_{self.icao}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        
        with open(filename, 'w', encoding='utf-8') as f:
            self._write_header(f)
            self._write_delays(f)
            self._write_errors(f)
            self._write_summary(f)
        
        print(f"Отчет сохранен: {filename}")
        return filename
    
    def _write_header(self, f):
        f.write("Отчет тестирования ADS-B IN\n")
        f.write(f"ICAO адрес: {self.icao}\n")
        f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Входных сообщений: {len(self.analyzer.input_messages)}\n")
        f.write(f"Выходных донесений: {len(self.analyzer.output_messages)}\n\n")
    
    def _write_delays(self, f):
        f.write("-" * 40 + "\n")
        f.write("Задержки формирования\n")
        f.write("-" * 40 + "\n")
        
        if self.analyzer.delays:
            delays_by_param = {}
            for d in self.analyzer.delays:
                param = d['param']
                if param not in delays_by_param:
                    delays_by_param[param] = []
                delays_by_param[param].append(d['delay'] * 1000)
            
            param_names = {
                'lat': 'Широта',
                'lon': 'Долгота',
                'baro_alt': 'Барометрическая высота',
                'geo_alt': 'Геометрическая высота',
                'ns_vel': 'Скорость (NS)',
                'ew_vel': 'Скорость (EW)'
            }
            
            f.write("Статистика по параметрам -\n")
            for param, delays in delays_by_param.items():
                name = param_names.get(param, param)
                min_delay = min(delays)
                max_delay = max(delays)
                
                f.write(f"  {name}:\n")
                f.write(f"    Задержек: {len(delays)}\n")
                f.write(f"    Мин: {min_delay:.1f} мс, Макс: {max_delay:.1f} мс\n\n")
            
            f.write(f"Всего превышений: {len(self.analyzer.delays)}\n\n")
        else:
            f.write("Нет данных о задержках\n")
        f.write("\n")
    
    def _write_errors(self, f):
        f.write("-" * 40 + "\n")
        f.write("Ошибки параметров\n")
        f.write("-" * 40 + "\n")
        
        if not self.analyzer.errors:
            f.write("Ошибок не обнаружено\n\n")
            return
        
        errors_by_report = defaultdict(lambda: defaultdict(list))
        for err in self.analyzer.errors:
            report_type = self._get_report_type(err.type)
            param = getattr(err, 'param', 'unknown')
            errors_by_report[report_type][param].append(err)
        
        for report_type, params in errors_by_report.items():
            f.write(f"\n{report_type}:\n")
            for param, err_list in params.items():
                f.write(f"  {param} ({len(err_list)} ошибок):\n")
                for err in err_list[:10]:
                    diff = getattr(err, 'diff', None)
                    if diff:
                        f.write(f"    t={err.time:.1f}с, diff={diff:.6f}\n")
                    else:
                        f.write(f"    t={err.time:.1f}с\n")
        f.write("\n")
    
    def _write_error_files(self):
        if not self.analyzer.errors:
            print("Нет ошибок для записи в файлы")
            return
        
        errors_by_report = defaultdict(lambda: defaultdict(list))
        for err in self.analyzer.errors:
            report_type = self._get_report_type(err.type)
            param = getattr(err, 'param', 'unknown')
            errors_by_report[report_type][param].append(err)
        
        for report_type, params in errors_by_report.items():
            report_dir = self.dirs.get(report_type, self.base_dir)
            
            for param, err_list in params.items():
                filename = os.path.join(report_dir, f'{param}_errors_{self.icao}.csv')
                
                with open(filename, 'w', encoding='utf-8-sig') as f:
                    if report_type == 'DUPLICATE':
                        f.write("Время,Значение\n")
                        for err in err_list:
                            value = getattr(err, 'value', '?')
                            f.write(f"{err.time:.3f},{value}\n")
                    else:
                        if param in ['lat', 'lon']:
                            f.write("Время,Ошибка (градусы),Входное значение,Выходное значение\n")
                        elif param in ['ns_vel', 'ew_vel']:
                            f.write("Время,Ошибка (узлы),Входное значение,Выходное значение\n")
                        elif param in ['baro_alt', 'geo_alt', 'selected_alt']:
                            f.write("Время,Ошибка (футы),Входное значение,Выходное значение\n")
                        elif param in ['selected_heading', 'heading']:
                            f.write("Время,Ошибка (градусы),Входное значение,Выходное значение\n")
                        else:
                            f.write("Время,Входное значение,Выходное значение\n")
                        
                        for err in err_list:
                            diff = getattr(err, 'diff', 0)
                            in_val = getattr(err, 'in_val', '?')
                            out_val = getattr(err, 'out_val', '?')
                            if param in ['lat', 'lon']:
                                f.write(f"{err.time:.3f},{diff:.6f},{in_val},{out_val}\n")
                            elif param in ['ns_vel', 'ew_vel']:
                                f.write(f"{err.time:.3f},{diff:.2f},{in_val},{out_val}\n")
                            elif param in ['baro_alt', 'geo_alt', 'selected_alt']:
                                f.write(f"{err.time:.3f},{diff:.2f},{in_val},{out_val}\n")
                            else:
                                f.write(f"{err.time:.3f},{in_val},{out_val}\n")
                
                print(f"Записано {len(err_list)} ошибок в {filename}")
    
    def _write_summary(self, f):
        f.write("-" * 40 + "\n")
        f.write("Итог\n")
        f.write("-" * 40 + "\n")
        
        total_errors = len(self.analyzer.errors)
        
        if total_errors == 0:
            if self.analyzer.delays:
                max_delay = max(d['delay'] for d in self.analyzer.delays)
                if max_delay <= 0.5:
                    f.write("Тестирование пройдено\n")
                    f.write("Параметры корректны, задержки в норме\n")
                else:
                    f.write("Тестирование пройдено частично\n")
                    f.write("Параметры корректны, но есть превышения задержек\n")
            else:
                f.write("Тестирование пройдено\n")
                f.write("Параметры корректны\n")
        else:
            f.write("Тестирование не пройдено\n")
            f.write(f"Обнаружено ошибок: {total_errors}\n")
            
            err_counts = defaultdict(lambda: defaultdict(int))
            for err in self.analyzer.errors:
                report_type = self._get_report_type(err.type)
                param = getattr(err, 'param', 'unknown')
                err_counts[report_type][param] += 1
            
            for report_type, params in err_counts.items():
                f.write(f"\n  {report_type}:\n")
                for param, count in params.items():
                    f.write(f"    - {param}: {count}\n")
    
    def _setup_plot(self, ax, xlabel, ylabel, title):
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)

    def plot_tsr(self):
        if not self.analyzer.tsr_messages:
            print("Нет данных TSR для построения графика")
            return
        
        times = [msg.timestamp for msg in self.analyzer.tsr_messages]
        alts = [msg.selected_alt for msg in self.analyzer.tsr_messages if msg.selected_alt]
        hdgs = [msg.selected_heading for msg in self.analyzer.tsr_messages if msg.selected_heading]
        
        in29_list = [msg for msg in self.analyzer.input_messages if msg.type == 'TYPE_29']
        in_times = [msg.timestamp for msg in in29_list]
        in_alts = [msg.selected_alt for msg in in29_list if msg.selected_alt]
        in_hdgs = [msg.selected_heading for msg in in29_list if msg.selected_heading]
        
        fig, axes = plt.subplots(2, 1, figsize=(14, 10))
        fig.suptitle(f'TSR_STRUCT параметры - ICAO {self.icao}', fontsize=14)
        
        ax1 = axes[0]
        if in_alts:
            ax1.plot(in_times[:len(in_alts)], in_alts, 'b.', markersize=4, label='TYPE_29 (входные)')
        if alts:
            ax1.plot(times[:len(alts)], alts, 'r.', markersize=4, label='TSR_STRUCT (выходные)')
        ax1.set_xlabel('Время (с)')
        ax1.set_ylabel('Выбранная высота (футы)')
        ax1.set_title('Выбранная высота')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        ax2 = axes[1]
        if in_hdgs:
            ax2.plot(in_times[:len(in_hdgs)], in_hdgs, 'b.', markersize=4, label='TYPE_29 (входные)')
        if hdgs:
            ax2.plot(times[:len(hdgs)], hdgs, 'r.', markersize=4, label='TSR_STRUCT (выходные)')
        ax2.set_xlabel('Время (с)')
        ax2.set_ylabel('Выбранный курс (градусы)')
        ax2.set_title('Выбранный курс')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        plt.tight_layout()
        filename = f'tsr_params_{self.icao}.png'
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"График TSR сохранен: {filename}")