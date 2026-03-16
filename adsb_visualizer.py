import matplotlib.pyplot as plt
from datetime import datetime
import os

class ADSBVisualizer:
    
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.icao = analyzer.icao
        self.thresholds = analyzer.thresholds
        
        self.errors_dir = f"errors_{self.icao}"
        if not os.path.exists(self.errors_dir):
            os.makedirs(self.errors_dir)
    
    def plot_all(self):
        self.plot_parameters()
        self.plot_heading()
        self.plot_errors()
        self.plot_changes_by_param()
        self._write_error_files()

    #курс
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
        plt.show()
        print(f"График курса сохранен: {filename}")
    
    #графики изменений
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
        
        plotted_params = []
        for param, changes in changes_by_param.items():
            if not changes:
                continue
            
            plotted_params.append(param)
            
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

                max_delay = max(delays_ms)
                min_delay = min(delays_ms)

                
                text = (f'Всего изменений: {len(delays_ms)}\n')
                
                plt.text(0.02, 0.95, text, transform=plt.gca().transAxes, 
                        verticalalignment='top', bbox=dict(boxstyle='round', 
                        facecolor='wheat', alpha=0.5), fontsize=10)
            
            plt.tight_layout()
            filename = f'changes_{param}_{self.icao}.png'
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            plt.show()
            print(f"График изменений для {title} сохранен: {filename}")
        
    
    def _write_error_files(self):
        if not self.analyzer.errors:
            print("Нет ошибок для записи в файлы")
            return
        
        errors_by_type = {}
        for err in self.analyzer.errors:
            if err.type not in errors_by_type:
                errors_by_type[err.type] = []
            errors_by_type[err.type].append(err)
        
        error_configs = {
            'coord': ('координаты', ['Время', 'Ошибка широты (м)', 'Ошибка долготы (м)']),
            'speed': ('скорость', ['Время', 'Ошибка (узлы)']),
            'heading': ('курс', ['Время', 'Ошибка (градусы)', 'Входной курс', 'Выходной курс']),
            'altitude': ('высота', ['Время', 'Ошибка (футы)', 'Барометрическая', 'Геометрическая'])
        }
        
        for err_type, err_list in errors_by_type.items():
            if err_type in error_configs:
                name, headers = error_configs[err_type]
                filename = f"{self.errors_dir}/{err_type}_errors_{self.icao}.csv"
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(','.join(headers) + '\n')
                    
                    for err in err_list:
                        if err_type == 'coord':
                            f.write(f"{err.time:.3f},{err.lat_diff:.2f},{err.lon_diff:.2f}\n")
                        elif err_type == 'speed':
                            f.write(f"{err.time:.3f},{err.diff:.2f}\n")
                        elif err_type == 'heading':
                            f.write(f"{err.time:.3f},{err.diff:.2f},{err.in_val:.2f},{err.out_val:.2f}\n")
                        elif err_type == 'altitude':
                            f.write(f"{err.time:.3f},{err.diff:.2f},{err.baro:.2f},{err.geo:.2f}\n")
                
                print(f"Записано {len(err_list)} ошибок {name} в {filename}")
    
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

    #графики параметров
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
        
        #Широта
        ax1 = axes[0, 0]
        if in_data['times']:
            ax1.plot(in_data['times'], in_data['lats'], 'b-', 
                    linewidth=1, label='TYPE_11/18', alpha=0.7)
        if out_data['times']:
            ax1.plot(out_data['times'], out_data['lats'], 'r.', 
                    markersize=3, label='SVR_STRUCT')
        self._setup_plot(ax1, 'Время (с)', 'Широта (градусы)', 'Широта')
        
        #Долгота
        ax2 = axes[0, 1]
        if in_data['times']:
            ax2.plot(in_data['times'], in_data['lons'], 'b-', 
                    linewidth=1, label='TYPE_11/18', alpha=0.7)
        if out_data['times']:
            ax2.plot(out_data['times'], out_data['lons'], 'r.', 
                    markersize=3, label='SVR_STRUCT')
        self._setup_plot(ax2, 'Время (с)', 'Долгота (градусы)', 'Долгота')
        
        #Баро высота
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
        
        #Гео высота
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
        
        #Скорость NS
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
        
        #Скорость EW
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
        plt.show()
        print(f"График параметров сохранен: {filename}")

    #графики ошибок
    def plot_errors(self):
        if not self.analyzer.errors:
            print("Нет ошибок для построения графиков")
            return
        
        errors_by_type = {}
        for err in self.analyzer.errors:
            if err.type not in errors_by_type:
                errors_by_type[err.type] = []
            errors_by_type[err.type].append(err)
        
        n_plots = len(errors_by_type)
        if n_plots == 0:
            return
        
        fig, axes = plt.subplots(n_plots, 1, figsize=(14, 4*n_plots))
        if n_plots == 1:
            axes = [axes]
        
        fig.suptitle(f'Ошибки параметров - ICAO {self.icao}', fontsize=14)
        
        plot_configs = {
            'coord': ('Ошибка координат', 'метры', 'blue', 
                     lambda e: max(e.lat_diff, e.lon_diff), 100),
            'speed': ('Ошибка скорости', 'узлы', 'red',
                     lambda e: e.diff, 2),
            'heading': ('Ошибка курса', 'градусы', 'green',
                       lambda e: e.diff, 2),
            'altitude': ('Ошибка высоты', 'футы', 'orange',
                        lambda e: e.diff, 2000),
            'baro_altitude': ('Ошибка барометрической высоты', 'футы', 'orange',
                            lambda e: e.diff, 2000),
            'geo_altitude': ('Ошибка геометрической высоты', 'футы', 'brown',
                           lambda e: e.diff, 2000)
        }
        
        for ax, (err_type, err_list) in zip(axes, errors_by_type.items()):
            if err_type in plot_configs:
                title, ylabel, color, get_val, threshold = plot_configs[err_type]
                
                times = [e.time for e in err_list]
                values = [get_val(e) for e in err_list]
                
                ax.plot(times, values, 'o', color=color, markersize=3)
                ax.axhline(y=threshold, color='r', linestyle='--', 
                          alpha=0.5, label=f'Порог {threshold}')
                ax.legend()
                
                ax.set_xlabel('Время (с)')
                ax.set_ylabel(ylabel)
                ax.set_title(title)
                ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        filename = f'errors_{self.icao}.png'
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        plt.show()
        print(f"График ошибок сохранен: {filename}")
    
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
            delays_ms = [d['delay'] * 1000 for d in self.analyzer.delays]
            
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
            
            exceed_total = len(delays_ms)
            f.write(f"Всего превышений: {exceed_total}\n\n")
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
        
        errors_by_type = {}
        for err in self.analyzer.errors:
            if err.type not in errors_by_type:
                errors_by_type[err.type] = []
            errors_by_type[err.type].append(err)
        
        for err_type, err_list in errors_by_type.items():
            if err_type == 'coord':
                f.write(f"\nКоординаты (>100 м): {len(err_list)}\n")
                for err in err_list[:10]:
                    f.write(f"  t={err.time:.1f}с: lat={err.lat_diff:.1f}м, "
                           f"lon={err.lon_diff:.1f}м\n")
            
            elif err_type == 'speed':
                f.write(f"\nСкорость (>2 узлов): {len(err_list)}\n")
                for err in err_list[:10]:
                    f.write(f"  t={err.time:.1f}с: {err.diff:.1f} узлов\n")
            
            elif err_type == 'heading':
                f.write(f"\nКурс (>2°): {len(err_list)}\n")
                for err in err_list[:10]:
                    f.write(f"  t={err.time:.1f}с: {err.diff:.1f}° "
                           f"(in={err.in_val:.1f}°, out={err.out_val:.1f}°)\n")
            
            elif err_type in ['altitude', 'baro_altitude', 'geo_altitude']:
                name = 'Барометрическая высота' if err_type == 'baro_altitude' else 'Геометрическая высота' if err_type == 'geo_altitude' else 'Высота'
                f.write(f"\n{name} (>2000 ft): {len(err_list)}\n")
                for err in err_list[:10]:
                    f.write(f"  t={err.time:.1f}с: {err.diff:.0f} ft "
                           f"(in={err.in_val:.0f}, out={err.out_val:.0f})\n")
        
        f.write("\n")
    
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
            
            err_counts = {}
            for err in self.analyzer.errors:
                err_counts[err.type] = err_counts.get(err.type, 0) + 1
            
            for err_type, count in err_counts.items():
                names = {
                    'coord': 'координаты', 
                    'speed': 'скорость',
                    'heading': 'курс', 
                    'altitude': 'высота',
                    'baro_altitude': 'барометрическая высота',
                    'geo_altitude': 'геометрическая высота'
                }
                f.write(f"  - {names.get(err_type, err_type)}: {count}\n")
    
    def _setup_plot(self, ax, xlabel, ylabel, title):
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)