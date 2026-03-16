#!/usr/bin/env python3
import sys
import os
from adsb_analyzer import ADSBAnalyzer
from adsb_visualizer import ADSBVisualizer

def main():
    if len(sys.argv) != 3:
        sys.exit(1)
    
    log_file = sys.argv[1]
    icao = sys.argv[2].upper()

    if not os.path.exists(log_file):
        print(f"\nФайл '{log_file}' не найден")
        sys.exit(1)

    analyzer = ADSBAnalyzer(icao)
    analyzer.parse_log_file(log_file)
    
    visualizer = ADSBVisualizer(analyzer)
    visualizer.plot_all()
    visualizer.gen_report()
    
    print(f"\nТестирование завершено. Отчет сохранен")

if __name__ == "__main__":
    main()