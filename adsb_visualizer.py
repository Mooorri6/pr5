import matplotlib.pyplot as plt
from datetime import datetime
import os

class ADSBVisualizer:
    
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.icao = analyzer.icao
        
        self.errors_dir = f"errors_{self.icao}"
        if not os.path.exists(self.errors_dir):
            os.makedirs(self.errors_dir)
    
    def plot_all(self):
        self.plot_parameters()
        self.plot_errors()
        self.plot_delays()
        self._write_error_files()
    
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
    
    def plot_parameters(self):
        """Графики параметров"""
        if not self.analyzer.output_messages:
            print("Недостаточно данных для построения графиков")
            return
        
        in_data = self._collect_input_data()
        out_data = self._collect_output_data()
        
        if not in_data['times'] and not out_data['times']:
            print("Нет данных для отображения")
            return
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Параметры ICAO {self.icao}', fontsize=14)
        
        # Широта
        if in_data['times']:
            ax1.plot(in_data['times'], in_data['lats'], 'b-', 
                    linewidth=1, label='TYPE_11/18', alpha=0.7)
        if out_data['times']:
            ax1.plot(out_data['times'], out_data['lats'], 'r.', 
                    markersize=3, label='SVR_STRUCT')
        self._setup_plot(ax1, 'Время (с)', 'Широта (градусы)', 'Широта')
        
        # Долгота
        if in_data['times']:
            ax2.plot(in_data['times'], in_data['lons'], 'b-', 
                    linewidth=1, label='TYPE_11/18', alpha=0.7)
        if out_data['times']:
            ax2.plot(out_data['times'], out_data['lons'], 'r.', 
                    markersize=3, label='SVR_STRUCT')
        self._setup_plot(ax2, 'Время (с)', 'Долгота (градусы)', 'Долгота')
        
        # Высота
        if in_data['alt_times'] and out_data['alt_times']:
            ax3.plot(in_data['alt_times'], in_data['alts'], 'b.', 
                    markersize=2, label='TYPE_11/18', alpha=0.7)
            ax3.plot(out_data['alt_times'], out_data['alts'], 'r.', 
                    markersize=3, label='SVR_STRUCT')
            self._setup_plot(ax3, 'Время (с)', 'Высота (футы)', 'Высота')
        
        # Курс
        if in_data['hdg_times'] and out_data['hdg_times']:
            ax4.plot(in_data['hdg_times'], in_data['hdgs'], 'b.', 
                    markersize=2, label='TYPE_19', alpha=0.7)
            ax4.plot(out_data['hdg_times'], out_data['hdgs'], 'r.', 
                    markersize=3, label='SVR_STRUCT')
            self._setup_plot(ax4, 'Время (с)', 'Курс (градусы)', 'Курс')
        
        plt.tight_layout()
        filename = f'param_{self.icao}.png'
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        plt.show()
        print(f"График параметров сохранен: {filename}")
    
    def _collect_input_data(self):
        """Сбор данных из входных сообщений"""
        data = {
            'times': [], 'lats': [], 'lons': [],
            'alt_times': [], 'alts': [],
            'hdg_times': [], 'hdgs': []
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
            
            elif msg.type == 'TYPE_19' and msg.speed_valid:
                heading = self.analyzer._calculate_heading(msg)
                if heading is not None:
                    data['hdg_times'].append(msg.timestamp)
                    data['hdgs'].append(heading)
        
        return data
    
    def _collect_output_data(self):
        """Сбор данных из выходных сообщений"""
        data = {
            'times': [], 'lats': [], 'lons': [],
            'alt_times': [], 'alts': [],
            'hdg_times': [], 'hdgs': []
        }
        
        for msg in self.analyzer.output_messages:
            if msg.type == 'SVR_STRUCT' and msg.lat is not None:
                if abs(msg.lat) > 0.0001 and abs(msg.lon) > 0.0001:
                    data['times'].append(msg.timestamp)
                    data['lats'].append(msg.lat)
                    data['lons'].append(msg.lon)
                    if msg.alt is not None:
                        data['alt_times'].append(msg.timestamp)
                        data['alts'].append(msg.alt)
                
                if msg.speed_valid:
                    heading = self.analyzer._calculate_heading(msg, is_svr=True)
                    if heading is not None:
                        data['hdg_times'].append(msg.timestamp)
                        data['hdgs'].append(heading)
        
        return data
    
    def plot_errors(self):
        """Графики ошибок"""
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
                        lambda e: e.diff, 2000)
        }
        
        for ax, (err_type, err_list) in zip(axes, errors_by_type.items()):
            if err_type in plot_configs:
                title, ylabel, color, get_val, threshold = plot_configs[err_type]
                
                times = [e.time for e in err_list]
                values = [get_val(e) for e in err_list]
                
                ax.plot(times, values, f'{color}o', markersize=3)
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
    
    def plot_delays(self):
        """График задержек"""
        if not self.analyzer.delays:
            print("Нет данных о задержках")
            return
        
        times = [d['time'] for d in self.analyzer.delays]
        delays = [d['delay'] * 1000 for d in self.analyzer.delays]
        
        plt.figure(figsize=(14, 6))
        plt.plot(times, delays, 'b-', linewidth=1)
        plt.xlabel('Время (с)')
        plt.ylabel('Задержка (мс)')
        plt.title(f'Задержки формирования донесений - ICAO {self.icao}')
        plt.grid(True, alpha=0.3)
        plt.axhline(y=500, color='r', linestyle='--', linewidth=1,
                   label='Предел 500 мс')
        plt.legend()
        
        filename = f'delays_{self.icao}.png'
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        plt.show()
        print(f"График задержек сохранен: {filename}")
    
    def generate_report(self):
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
            f.write(f"Измерений: {len(self.analyzer.delays)}\n")
            f.write(f"Минимальная: {min(delays_ms):.1f} мс\n")
            f.write(f"Максимальная: {max(delays_ms):.1f} мс\n")
            f.write(f"Средняя: {sum(delays_ms)/len(delays_ms):.1f} мс\n")
            
            exceed = sum(1 for d in delays_ms if d > 500)
            f.write(f"Превышений 500 мс: {exceed}\n\n")
            
            if exceed > 0:
                f.write("Детали:\n")
                for d in self.analyzer.delays:
                    if d['delay'] * 1000 > 500:
                        f.write(f"  t={d['time']:.1f}с: {d['delay']*1000:.1f} мс\n")
        else:
            f.write("Нет данных о задержках\n")
        f.write("\n")
    
    def _write_errors(self, f):
        """Запись информации об ошибках"""
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
            
            elif err_type == 'altitude':
                f.write(f"\nВысота (>2000 ft): {len(err_list)}\n")
                for err in err_list[:10]:
                    f.write(f"  t={err.time:.1f}с: {err.diff:.0f} ft "
                           f"(baro={err.baro:.0f}, geo={err.geo:.0f})\n")
        
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
                names = {'coord': 'координаты', 'speed': 'скорость',
                        'heading': 'курс', 'altitude': 'высота'}
                f.write(f"  - {names.get(err_type, err_type)}: {count}\n")
        
    
    def _setup_plot(self, ax, xlabel, ylabel, title):
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)