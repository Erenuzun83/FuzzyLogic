import sys
import logging
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox, QDialog,
    QDialogButtonBox, QSpinBox, QDoubleSpinBox, QFrame, QCheckBox, QScrollArea, QFileDialog,
    QGroupBox, QFormLayout
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QTimer, pyqtSignal, Qt, QSettings
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import copy
import time
import json
import os
from datetime import datetime
from snap7.client import Client
from snap7.util import get_real, set_real

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StaticFuzzyPlot(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        fig = Figure(figsize=(4, 3), dpi=72)
        fig.tight_layout(pad=2.5)
        self.canvas = FigureCanvas(fig)
        self.ax = fig.add_subplot(111)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.canvas)
        self.update_plot(settings)

    def update_plot(self, settings):
        self.ax.clear()
        all_points = [p for points_list in settings['points'].values() for p in points_list]
        max_abs_val = max(abs(p) for p in all_points) if all_points else 5
        universe_max = np.ceil(max_abs_val) + 1
        colors = {'NH': 'red', 'NL': 'orange', 'Z': 'green', 'PL': 'cyan', 'PH': 'blue'}
        for name, points in settings['points'].items():
            self.ax.plot([points[0], points[1], points[2]], [0, 1, 0], color=colors.get(name, 'black'), label=name)
        self.ax.set_xlim(-universe_max, universe_max)
        self.ax.set_ylim(-0.1, 1.2)
        self.ax.set_title("Anlık Girdi Fonksiyonları", fontsize=10)
        self.ax.set_xlabel("Fark", fontsize=8)
        self.ax.set_ylabel("Üyelik", fontsize=8)
        self.ax.tick_params(axis='both', which='major', labelsize=7)
        self.ax.grid(True, linestyle='--', linewidth='0.5')
        self.ax.legend(fontsize=7)
        self.canvas.draw()

class InteractiveFuzzyPlot(QWidget):
    settingsChanged = pyqtSignal(dict)
    def __init__(self, settings, parent=None):
        super().__init__(parent); self.settings = settings; self.selected_point = None
        fig = Figure(figsize=(8, 4)); self.canvas = FigureCanvas(fig); self.ax = fig.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas, self); layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar); layout.addWidget(self.canvas); self.plot_membership_functions()
        self.canvas.mpl_connect('button_press_event', self.on_press); self.canvas.mpl_connect('motion_notify_event', self.on_motion); self.canvas.mpl_connect('button_release_event', self.on_release)
    def plot_membership_functions(self):
        xlim = self.ax.get_xlim(); ylim = self.ax.get_ylim()
        self.ax.clear()
        is_zoomed = len(self.toolbar._nav_stack) > 1; universe_max = self.settings.get('universe_max', 20)
        colors = {'NH': 'red', 'NL': 'orange', 'Z': 'green', 'PL': 'cyan', 'PH': 'blue'}
        for name, points in self.settings['points'].items():
            self.ax.plot([points[0], points[1], points[2]], [0, 1, 0], marker='o', color=colors.get(name, 'black'), label=name, markersize=8)
            try:
                area = 0.5 * (abs(points[2] - points[0])) * 1.0; self.ax.text(points[1], 1.05, f'Alan: {area:.2f}', ha='center', va='bottom', fontsize=8)
            except Exception: pass
        if not is_zoomed: self.ax.set_xlim(-universe_max, universe_max); self.ax.set_ylim(-0.1, 1.2)
        else: self.ax.set_xlim(xlim); self.ax.set_ylim(ylim)
        self.ax.set_xlabel("Fark (Set Seviye - Anlık Seviye)"); self.ax.set_ylabel("Üyelik Derecesi"); self.ax.set_title("Girdi Üyelik Fonksiyonlarını Sürükleyerek Ayarlayın")
        self.ax.minorticks_on(); self.ax.grid(which='major', linestyle='-', linewidth='0.5'); self.ax.grid(which='minor', linestyle=':', linewidth='0.5')
        handles, labels = self.ax.get_legend_handles_labels(); by_label = dict(zip(labels, handles))
        self.ax.legend(by_label.values(), by_label.keys()); self.canvas.draw_idle()
    def find_closest_point(self, event):
        min_dist = float('inf'); closest_point = None
        if event.xdata is None or event.ydata is None: return None
        for name, points in self.settings['points'].items():
            for i, (px, py) in enumerate(zip(points, [0, 1, 0])):
                dist = np.sqrt((event.x - self.ax.transData.transform((px, py))[0])**2 + (event.y - self.ax.transData.transform((px, py))[1])**2)
                if dist < 10 and dist < min_dist: min_dist = dist; closest_point = (name, i)
        return closest_point
    def on_press(self, event):
        if self.toolbar.mode: return
        self.selected_point = self.find_closest_point(event)
    def on_motion(self, event):
        if self.selected_point and event.xdata is not None:
            name, idx = self.selected_point; new_x = event.xdata; points = self.settings['points'][name]
            if idx == 0 and new_x >= points[1]: new_x = points[1] - 0.1
            if idx == 2 and new_x <= points[1]: new_x = points[1] + 0.1
            if idx == 1 and (new_x <= points[0] or new_x >= points[2]): return
            if name == 'Z' and idx == 1: return
            self.settings['points'][name][idx] = new_x; self.plot_membership_functions()
    def on_release(self, event):
        if self.selected_point: self.selected_point = None; self.settingsChanged.emit(self.settings)

class FuzzyGraphSettingsDialog(QDialog):
    settingsApplied = pyqtSignal(dict)
    def __init__(self, current_settings, parent_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Grafiksel Bulanık Mantık Ayarları")
        self.setMinimumWidth(850)
        self.final_settings = copy.deepcopy(current_settings)
        self.qt_settings = parent_settings
        layout = QVBoxLayout(self)
        opt_frame = QFrame()
        opt_frame.setFrameShape(QFrame.Shape.StyledPanel)
        opt_frame_layout = QVBoxLayout(opt_frame)
        opt_frame_layout.setContentsMargins(5, 5, 5, 5)
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addWidget(QLabel("<b>Otomatik Optimizasyon Parametreleri</b>"))
        top_bar_layout.addStretch()
        self.toggle_button = QPushButton("Gizle ▲")
        self.toggle_button.setCheckable(True)
        self.toggle_button.clicked.connect(self.toggle_visibility)
        top_bar_layout.addWidget(self.toggle_button)
        opt_frame_layout.addLayout(top_bar_layout)
        self.opt_container = QWidget()
        opt_layout = QGridLayout(self.opt_container)
        self.min_level_spin = QDoubleSpinBox(); self.min_level_spin.setRange(0, 10000)
        self.max_level_spin = QDoubleSpinBox(); self.max_level_spin.setRange(0, 10000)
        self.set_level_spin = QDoubleSpinBox(); self.set_level_spin.setRange(0, 10000)
        opt_layout.addWidget(QLabel("Min Seviye:"), 0, 0); opt_layout.addWidget(self.min_level_spin, 0, 1)
        opt_layout.addWidget(QLabel("Max Seviye:"), 0, 2); opt_layout.addWidget(self.max_level_spin, 0, 3)
        opt_layout.addWidget(QLabel("Set Seviye:"), 1, 0); opt_layout.addWidget(self.set_level_spin, 1, 1)
        self.aggressiveness_spin = QDoubleSpinBox(); self.aggressiveness_spin.setRange(0.5, 5.0); self.aggressiveness_spin.setSingleStep(0.1)
        self.precision_spin = QDoubleSpinBox(); self.precision_spin.setRange(0.5, 3.0); self.precision_spin.setSingleStep(0.1)
        opt_layout.addWidget(QLabel("Agresiflik (>1 Daha Hızlı):"), 2, 0); opt_layout.addWidget(self.aggressiveness_spin, 2, 1)
        opt_layout.addWidget(QLabel("Hassasiyet (>1 Daha Hassas):"), 2, 2); opt_layout.addWidget(self.precision_spin, 2, 3)
        self.scale_spinbox = QSpinBox(); self.scale_spinbox.setRange(5, 500)
        opt_layout.addWidget(QLabel("Grafik Skalası (Maks. Fark):"), 3, 0)
        opt_layout.addWidget(self.scale_spinbox, 3, 1, 1, 3)
        self.optimize_btn = QPushButton("Grafiği ve Kuralları Optimize Et")
        opt_layout.addWidget(self.optimize_btn, 4, 0, 1, 4)
        opt_frame_layout.addWidget(self.opt_container)
        layout.addWidget(opt_frame)
        self.plot_widget = InteractiveFuzzyPlot(self.final_settings); layout.addWidget(self.plot_widget)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Apply); layout.addWidget(self.button_box)
        self.button_box.clicked.connect(self.handle_button_click)
        self.scale_spinbox.valueChanged.connect(self.update_plot_scale); self.plot_widget.settingsChanged.connect(self.on_plot_settings_changed); self.optimize_btn.clicked.connect(self.optimize_graph)
        self.load_dialog_settings(current_settings)
    def toggle_visibility(self):
        self.opt_container.setVisible(not self.toggle_button.isChecked())
        self.toggle_button.setText("Göster ▼" if self.toggle_button.isChecked() else "Gizle ▲")
        self.adjustSize()
    def update_from_parent(self, new_settings):
        self.final_settings = copy.deepcopy(new_settings)
        self.plot_widget.settings = self.final_settings; self.plot_widget.plot_membership_functions()
    def load_dialog_settings(self,s):
        self.scale_spinbox.setValue(s.get('universe_max',5));
        self.min_level_spin.setValue(self.qt_settings.value("dialog/opt_min", s.get('opt_min', 0), type=float))
        self.max_level_spin.setValue(self.qt_settings.value("dialog/opt_max", s.get('opt_max', 5), type=float))
        self.set_level_spin.setValue(self.qt_settings.value("dialog/opt_set", s.get('opt_set', 3.3), type=float))
        self.aggressiveness_spin.setValue(s.get('opt_aggr',4.0)); self.precision_spin.setValue(s.get('opt_prec',2.0))
    def apply_changes(self):
        self.qt_settings.setValue("dialog/opt_min", self.min_level_spin.value())
        self.qt_settings.setValue("dialog/opt_max", self.max_level_spin.value())
        self.qt_settings.setValue("dialog/opt_set", self.set_level_spin.value())
        self.final_settings['opt_aggr'] = self.aggressiveness_spin.value()
        self.final_settings['opt_prec'] = self.precision_spin.value()
        self.settingsApplied.emit(self.final_settings)
    def handle_button_click(self, button):
        role = self.button_box.buttonRole(button)
        if role == QDialogButtonBox.ButtonRole.AcceptRole: self.apply_changes(); self.accept()
        elif role == QDialogButtonBox.ButtonRole.ApplyRole: self.apply_changes()
        elif role == QDialogButtonBox.ButtonRole.RejectRole: self.reject()
        
    def optimize_graph(self):
        min_l,max_l,set_l=self.min_level_spin.value(),self.max_level_spin.value(),self.set_level_spin.value()
        if not (min_l <= set_l <= max_l): QMessageBox.warning(self,"Hata","Set Seviyesi, Min ve Max Seviye arasında olmalıdır."); return
        
        agg_factor=self.aggressiveness_spin.value();prec_factor=self.precision_spin.value();prec_multiplier=1.0/prec_factor
        total_range=max_l-min_l if max_l>min_l else 1;max_pos_error=set_l-min_l;max_neg_error=set_l-max_l;new_max_universe=max(abs(max_pos_error),abs(max_neg_error),1.0);self.scale_spinbox.setValue(int(np.ceil(new_max_universe)))
        
        z_width=(total_range*0.05)*prec_multiplier
        
        agg_multiplier = 1.0 / agg_factor
        pl_peak=(max_pos_error*0.4)*agg_multiplier; pl_end=(max_pos_error*0.8)*agg_multiplier
        ph_start=(max_pos_error*0.7)*agg_multiplier
        nl_peak=(max_neg_error*0.4)*agg_multiplier; nl_end=(max_neg_error*0.8)*agg_multiplier
        nh_start=(max_neg_error*0.7)*agg_multiplier
        
        pl_peak=max(pl_peak,z_width+0.01); nl_peak=min(nl_peak,-z_width-0.01)
        
        new_points={'Z':[-z_width,0,z_width],'PL':[z_width,pl_peak,pl_end],'PH':[ph_start,max_pos_error,max_pos_error],'NL':[nl_end,nl_peak,-z_width],'NH':[max_neg_error,max_neg_error,nh_start]}
        self.final_settings['points']=new_points;self.final_settings['universe_max']=int(np.ceil(new_max_universe));self.final_settings['control_range']=total_range
        
        valves = self.final_settings.get('valves', []); fill_valve = valves[0]['name'] if len(valves) > 0 else None; drain_valve = valves[1]['name'] if len(valves) > 1 else None
        raw_rules = { 'PH_P':{'fill':1.0,'drain':0},'PH_Z':{'fill':0.9,'drain':0},'PH_N':{'fill':0.7,'drain':0},'PL_P':{'fill':0.6,'drain':0},'PL_Z':{'fill':0.3,'drain':0},'PL_N':{'fill':0.1,'drain':0},'Z_P':{'fill':0.15,'drain':0},'Z_Z':{'fill':0,'drain':0},'Z_N':{'fill':0,'drain':0.15},'NL_P':{'fill':0,'drain':0.1},'NL_Z':{'fill':0,'drain':0.3},'NL_N':{'fill':0,'drain':0.6},'NH_P':{'fill':0,'drain':0.7},'NH_Z':{'fill':0,'drain':0.9},'NH_N':{'fill':1.0,'drain':1.0},}
        optimized_rules = {}
        for key, vals in raw_rules.items():
            rule_entry = {}
            if fill_valve: rule_entry[fill_valve] = vals['fill']
            if drain_valve: rule_entry[drain_valve] = vals['drain']
            optimized_rules[key] = rule_entry
        self.final_settings['outputs'] = optimized_rules
        self.plot_widget.settings = self.final_settings; self.plot_widget.plot_membership_functions();QMessageBox.information(self,"Başarılı","Giriş grafiği ve kural tablosu optimize edildi.")

    def update_plot_scale(self,new_max_value):
        old_max_value=self.final_settings.get('universe_max',new_max_value)
        if new_max_value<old_max_value and old_max_value !=0:
            scaling_factor=new_max_value/old_max_value
            for name in self.final_settings['points']:self.final_settings['points'][name]=[p*scaling_factor for p in self.final_settings['points'][name]]
        self.final_settings['universe_max']=new_max_value; self.plot_widget.settings = self.final_settings; self.plot_widget.plot_membership_functions()
    def on_plot_settings_changed(self,new_settings):self.final_settings=copy.deepcopy(new_settings)

class ValveSettingsDialog(QDialog):
    def __init__(self, valves, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vana Konfigürasyonu"); self.setMinimumWidth(500); self.valves = copy.deepcopy(valves); self.widgets = []
        self.main_layout = QVBoxLayout(self); header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<b>Vana Adı</b>"), 3); header_layout.addWidget(QLabel("<b>Min Çıkış</b>"), 1); header_layout.addWidget(QLabel("<b>Max Çıkış</b>"), 1)
        self.main_layout.addLayout(header_layout); self.valve_layout = QVBoxLayout()
        for valve_data in self.valves: self.add_valve_row(valve_data)
        self.main_layout.addLayout(self.valve_layout); button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_and_accept); button_box.rejected.connect(self.reject); self.main_layout.addWidget(button_box)
    def add_valve_row(self, valve_data):
        row_layout = QHBoxLayout(); name_edit = QLineEdit(valve_data['name'])
        min_spin = QDoubleSpinBox(); min_spin.setRange(-10000, 10000); min_spin.setValue(valve_data['min_out'])
        max_spin = QDoubleSpinBox(); max_spin.setRange(-10000, 10000); max_spin.setValue(valve_data['max_out'])
        row_layout.addWidget(name_edit, 3); row_layout.addWidget(min_spin, 1); row_layout.addWidget(max_spin, 1)
        container = QWidget(); container.setLayout(row_layout); self.valve_layout.addWidget(container)
        self.widgets.append((name_edit, min_spin, max_spin))
    def save_and_accept(self):
        new_valves = []
        for i, (name_edit, min_spin, max_spin) in enumerate(self.widgets):
            if not name_edit.text().strip(): QMessageBox.warning(self, "Hata", "Vana isimleri boş olamaz."); return
            original_offset = self.valves[i].get('offset')
            new_valve_data = {'name': name_edit.text(),'min_out': min_spin.value(),'max_out': max_spin.value()}
            if original_offset is not None: new_valve_data['offset'] = original_offset
            new_valves.append(new_valve_data)
        self.valves = new_valves; self.accept()

class RuleSettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vana Açıklık Oranları (0-1 Skalası)"); self.setMinimumWidth(800)
        self.final_settings = copy.deepcopy(current_settings); self.valves = self.final_settings.get('valves', [])
        self.input_labels = ['NH', 'NL', 'Z', 'PL', 'PH']; self.delta_labels = ['N (Düşüyor)', 'Z (Sabit)', 'P (Yükseliyor)']; self.widgets = {}
        layout = QGridLayout(self); layout.addWidget(QLabel("<b>HATA (Error)</b>"), 0, 1, alignment=Qt.AlignmentFlag.AlignCenter); layout.addWidget(QLabel("<b>HATA DEĞİŞİMİ (dE)</b>"), 1, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        for i, label in enumerate(self.input_labels): layout.addWidget(QLabel(f"<b>{label}</b>"), 0, i + 2, alignment=Qt.AlignmentFlag.AlignCenter)
        for i, d_label in enumerate(self.delta_labels): layout.addWidget(QLabel(f"<b>{d_label}</b>"), i + 2, 1, alignment=Qt.AlignmentFlag.AlignRight)
        for i, d_label_key in enumerate(['N', 'Z', 'P']):
            for j, label in enumerate(self.input_labels):
                key = f"{label}_{d_label_key}"; self.widgets[key] = {}
                cell_widget = QWidget(); cell_layout = QVBoxLayout(cell_widget); rule_outputs = self.final_settings['outputs'].get(key, {})
                for valve in self.valves:
                    valve_name = valve['name']; cell_layout.addWidget(QLabel(f"{valve_name}:"))
                    spinbox = QDoubleSpinBox(); spinbox.setRange(0.0, 1.0); spinbox.setDecimals(2); spinbox.setSingleStep(0.05)
                    spinbox.setValue(rule_outputs.get(valve_name, 0.0)); cell_layout.addWidget(spinbox); self.widgets[key][valve_name] = spinbox
                layout.addWidget(cell_widget, i + 2, j + 2)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); button_box.accepted.connect(self.save_and_accept); button_box.rejected.connect(self.reject); layout.addWidget(button_box, len(self.delta_labels) + 2, 0, 1, len(self.input_labels) + 2)
    def save_and_accept(self):
        for key, valve_widgets in self.widgets.items():
            if key not in self.final_settings['outputs']: self.final_settings['outputs'][key] = {}
            for valve_name, spinbox in valve_widgets.items(): self.final_settings['outputs'][key][valve_name] = spinbox.value()
        self.accept()

class FuzzyPIDController:
    def __init__(self, s):
        umax = s.get('universe_max', 100); p_conf = {n: list(pts) for n, pts in s['points'].items()}; valves_conf = s.get('valves', [])
        p_conf['NH'][0] = -umax; p_conf['PH'][2] = umax
        self.error_antecedent = ctrl.Antecedent(np.arange(-umax, umax + 0.5, 0.5), 'error'); [self.error_antecedent.__setitem__(n, fuzz.trimf(self.error_antecedent.universe, p)) for n, p in p_conf.items()]
        delta_umax = umax / 4; delta_error = ctrl.Antecedent(np.arange(-delta_umax, delta_umax + 0.1, 0.1), 'delta_error')
        delta_error['N'] = fuzz.trimf(delta_error.universe, [-delta_umax, -delta_umax, 0]); delta_error['Z'] = fuzz.trimf(delta_error.universe, [-delta_umax * 0.2, 0, delta_umax * 0.2]); delta_error['P'] = fuzz.trimf(delta_error.universe, [0, delta_umax, delta_umax])
        self.consequents = {}
        for valve in valves_conf:
            self.consequents[valve['name']] = ctrl.Consequent(np.arange(0, 1.01, 0.01), valve['name'])
        rules = []; output_values = s.get('outputs', {})
        for err_label in ['NH', 'NL', 'Z', 'PL', 'PH']:
            for delta_label in ['N', 'Z', 'P']:
                key = f"{err_label}_{delta_label}"; rule_outputs = output_values.get(key, {})
                consequent_tuple = []
                for valve_name, consequent_obj in self.consequents.items():
                    val = rule_outputs.get(valve_name, 0.0); consequent_obj[key] = fuzz.trimf(consequent_obj.universe, [val - 0.01, val, val + 0.01]); consequent_tuple.append(consequent_obj[key])
                if consequent_tuple: rule = ctrl.Rule(self.error_antecedent[err_label] & delta_error[delta_label], tuple(consequent_tuple)); rules.append(rule)
        self.simulation = ctrl.ControlSystemSimulation(ctrl.ControlSystem(rules))
    def compute(self, current_error, delta_error_val):
        try: self.simulation.input['error'] = current_error; self.simulation.input['delta_error'] = delta_error_val; self.simulation.compute(); return self.simulation.output
        except Exception as ex: logging.error(f"Hesaplama hatası: {ex}"); return {name: 0.0 for name in self.consequents.keys()}

class PLCManager:
    def __init__(self): self.client=Client(); self.is_connected=False
    def connect(self,ip,r,s):
        try: self.client.connect(ip,r,s); self.is_connected = self.client.get_connected()
        except Exception as e: self.is_connected=False; logging.error(f"PLC hata: {e}"); return False, f"Hata: {e}"
        return (True, "Başarılı.") if self.is_connected else (False, "Bağlantı kurulamadı.")
    def disconnect(self):
        if self.is_connected: self.client.disconnect(); self.is_connected=False; logging.info("PLC bağlantısı kesildi.")
    def read_real(self,d,o):
        try: return get_real(self.client.db_read(d,o,4),0)
        except Exception as e: logging.error(f"Okuma hatası (DB{d},Off{o}): {e}"); raise
    def write_real(self,d,o,v):
        try: data=bytearray(4); set_real(data,0,v); self.client.db_write(d,o,data)
        except Exception as e: logging.error(f"Yazma hatası (DB{d},Off{o}): {e}"); raise

class MainWindow(QMainWindow):
    fuzzy_settings_updated = pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fuzzy Logic Kontrolcü")
        self.setMinimumSize(1024, 768)
        self.settings = QSettings("MyCompany", "FuzzyPIDTankControl_Advanced_v5") # Versiyon güncellendi
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self.plc_manager = PLCManager(); self.fuzzy_settings = {}; self.last_error = 0.0
        self.valve_addr_inputs = {}; self.valve_output_labels = {}
        self.best_performance_score = 0.0; self.best_fuzzy_points = None

        # --- Temel Durum Değişkenleri ---
        self.current_set_level = 0.0; self.current_actual_level = 0.0; self.current_error = 0.0
        
        # --- Gelişmiş Adaptasyon Durum Değişkenleri (STATE MACHINE) ---
        self.adaptation_mode = "IDLE"           # Current state: IDLE, STABLE, SETTLE, DISTURBANCE_WAIT, POST_DISTURBANCE_OBSERVE, AGGRESSIVE_CORRECTION, PRECISION_OBSERVE, FINE_TUNE, STABLE_LOCKED
        self.adaptation_mode_end_time = 0.0     # Timer for states
        self.adaptation_mode_storage = {}       # Dictionary to pass data between states (e.g., pre-aggressive gain)
        self.is_adapted = False                 # Flag to indicate successful adaptation
        self.is_in_fine_tune_observation = False # Sub-state for FINE_TUNE
        self.last_adaptation_info = {}          
        self.gain_adaptation_multipliers = {}
        self.frozen_fuzzy_outputs = {}
        self.locked_stable_outputs = {}        
        self.drift_correction_timer = 0.0
        self.drift_adjustment_values = {}
        self.INITIAL_SETTLING_TIMEOUT = 60
        self.graph_dialog = None
        
        self.setup_ui()
        self.control_timer = QTimer(self); self.control_timer.timeout.connect(self.run_control_cycle)
        self.plc_read_timer = QTimer(self); self.plc_read_timer.timeout.connect(self.read_and_update_ui)
        self.disturbance_countdown_timer = QTimer(self); self.disturbance_countdown_timer.timeout.connect(self.update_countdown_label)
        
        self.load_settings()
        if self.best_fuzzy_points: self.fuzzy_settings['points'] = copy.deepcopy(self.best_fuzzy_points)
        else: self.best_fuzzy_points = copy.deepcopy(self.fuzzy_settings['points'])
        self.rebuild_dynamic_ui(); self.fuzzy_controller = FuzzyPIDController(self.fuzzy_settings)
        self.static_plot_widget.update_plot(self.fuzzy_settings)

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        top_layout = QHBoxLayout()
        left_panel = QFrame()
        left_panel.setFrameShape(QFrame.Shape.StyledPanel)
        left_panel.setMaximumWidth(400)
        left_panel_layout = QVBoxLayout(left_panel)
        left_panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        plc_group_box = QGroupBox("PLC Bağlantısı")
        plc_form_layout = QFormLayout(plc_group_box)
        self.ip_input = QLineEdit()
        self.rack_input = QLineEdit()
        self.slot_input = QLineEdit()
        self.btn_connect = QPushButton("PLC'ye Bağlan")
        self.btn_connect.setCheckable(True)
        self.btn_connect.setMinimumHeight(35)
        self.btn_connect.clicked.connect(self.toggle_plc_connection)
        plc_form_layout.addRow("IP Adresi:", self.ip_input)
        plc_form_layout.addRow("Rack:", self.rack_input)
        plc_form_layout.addRow("Slot:", self.slot_input)
        plc_form_layout.addRow(self.btn_connect)
        left_panel_layout.addWidget(plc_group_box)
        db_group_box = QGroupBox("PLC Adresleri")
        db_form_layout = QFormLayout(db_group_box)
        self.db_num_input = QLineEdit()
        self.set_level_addr_input = QLineEdit()
        self.levelmeter_addr_input = QLineEdit()
        db_form_layout.addRow("DB Numarası:", self.db_num_input)
        db_form_layout.addRow("Set Seviye Adresi:", self.set_level_addr_input)
        db_form_layout.addRow("Levelmeter Adresi:", self.levelmeter_addr_input)
        self.valve_addr_frame = QWidget()
        self.valve_addr_layout = QFormLayout(self.valve_addr_frame)
        self.valve_addr_layout.setContentsMargins(0, 0, 0, 0)
        db_form_layout.addRow(self.valve_addr_frame)
        left_panel_layout.addWidget(db_group_box)
        self.learning_enabled_checkbox = QCheckBox("Otomatik Ayar (Öğrenme)")
        self.learning_enabled_checkbox.setChecked(True)
        left_panel_layout.addWidget(self.learning_enabled_checkbox)
        static_plot_group = QGroupBox("Girdi Fonksiyonları Önizleme")
        static_plot_layout = QVBoxLayout(static_plot_group)
        self.static_plot_widget = StaticFuzzyPlot(self.get_default_fuzzy_settings())
        static_plot_layout.addWidget(self.static_plot_widget)
        left_panel_layout.addWidget(static_plot_group)
        left_panel_layout.addStretch()
        right_panel = QWidget()
        right_panel_layout = QVBoxLayout(right_panel)
        set_level_group = QGroupBox("Manuel Set Değeri")
        set_level_layout = QHBoxLayout(set_level_group)
        self.set_level_value_spin = QDoubleSpinBox()
        self.set_level_value_spin.setRange(0, 10000)
        self.set_level_value_spin.setMinimumHeight(50)
        font = self.set_level_value_spin.font(); font.setPointSize(20); font.setBold(True); self.set_level_value_spin.setFont(font)
        self.set_level_value_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_send_set_level = QPushButton("GÖNDER")
        self.btn_send_set_level.setMinimumHeight(50)
        font = self.btn_send_set_level.font(); font.setPointSize(12); font.setBold(True); self.btn_send_set_level.setFont(font)
        self.btn_send_set_level.clicked.connect(self.write_set_level_to_plc)
        set_level_layout.addWidget(self.set_level_value_spin, 2)
        set_level_layout.addWidget(self.btn_send_set_level, 1)
        right_panel_layout.addWidget(set_level_group)
        status_group = QGroupBox("Sistem Durumu")
        font = status_group.font(); font.setPointSize(12); font.setBold(True); status_group.setFont(font)
        status_layout = QGridLayout(status_group)
        self.lbl_set_level = QLabel("Set Seviye: -")
        self.lbl_actual_level = QLabel("Anlık Seviye: -")
        self.lbl_error = QLabel("Fark: -")
        #self.lbl_best_performance = QLabel(f"En İyi Performans: N/A")
        status_labels = [self.lbl_set_level, self.lbl_actual_level, self.lbl_error]
        for i, label in enumerate(status_labels):
            label.setFrameShape(QFrame.Shape.StyledPanel)
            label.setFrameShadow(QFrame.Shadow.Sunken)
            label.setMinimumHeight(60)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            font = label.font(); font.setPointSize(14); font.setBold(True); label.setFont(font)
            label.setWordWrap(True)
            status_layout.addWidget(label, 0, i)
        right_panel_layout.addWidget(status_group)
        buttons_group = QGroupBox("Kontrol ve Ayarlar")
        buttons_layout = QGridLayout(buttons_group)
        self.btn_start_stop = QPushButton("Kontrolü Başlat"); self.btn_start_stop.setCheckable(True); self.btn_start_stop.setEnabled(False); self.btn_start_stop.clicked.connect(self.toggle_control_loop)
        self.btn_fuzzy_settings = QPushButton("Giriş Grafiği Ayarları"); self.btn_fuzzy_settings.clicked.connect(self.open_fuzzy_graph_settings)
        self.btn_rule_settings = QPushButton("Kural Tablosu Ayarları"); self.btn_rule_settings.clicked.connect(self.open_rule_settings)
        self.btn_valve_settings = QPushButton("Vana Ayarları"); self.btn_valve_settings.clicked.connect(self.open_valve_settings)
        self.btn_save_as = QPushButton("Ayarları Farklı Kaydet..."); self.btn_save_as.clicked.connect(self.save_settings_as)
        self.btn_start_stop.setMinimumHeight(70)
        font = self.btn_start_stop.font(); font.setPointSize(14); self.btn_start_stop.setFont(font)
        buttons_layout.addWidget(self.btn_start_stop, 0, 0, 1, 2)
        small_buttons = [self.btn_fuzzy_settings, self.btn_rule_settings, self.btn_valve_settings, self.btn_save_as]
        for i, btn in enumerate(small_buttons):
            btn.setMinimumHeight(50)
            buttons_layout.addWidget(btn, (i // 2) + 1, i % 2)
        right_panel_layout.addWidget(buttons_group)
        self.valve_output_frame = QGroupBox("Vana Çıkışları")
        self.valve_output_layout = QGridLayout(self.valve_output_frame)
        right_panel_layout.addWidget(self.valve_output_frame)
        
        # --- YENİ: Başlık ve Gizle/Göster Butonu ---
        adapt_header_layout = QHBoxLayout()
        adapt_header_layout.addWidget(QLabel("<b>Adaptasyon Ayarları</b>"))
        adapt_header_layout.addStretch()
        self.toggle_adapt_settings_button = QPushButton("Gizle ▲")
        self.toggle_adapt_settings_button.setCheckable(True)
        self.toggle_adapt_settings_button.clicked.connect(self.toggle_adaptation_settings)
        self.toggle_adapt_settings_button.setFixedWidth(100) # Buton boyutunu sabitle
        adapt_header_layout.addWidget(self.toggle_adapt_settings_button)
        right_panel_layout.addLayout(adapt_header_layout)

        # --- GÜNCELLEME: `adapt_group` artık bir class üyesi ---
        self.adapt_group = QGroupBox() # Başlık kaldırıldı, çerçeve olarak kullanılacak
        main_adapt_layout = QVBoxLayout(self.adapt_group)
        
        form_widget = QWidget()
        adapt_layout = QFormLayout(form_widget)
        adapt_layout.setContentsMargins(0,0,0,0)

        self.disturbance_threshold_spin = QDoubleSpinBox(); self.disturbance_threshold_spin.setRange(0.01, 1000.0); self.disturbance_threshold_spin.setSingleStep(0.01); self.disturbance_threshold_spin.setDecimals(3)
        self.disturbance_delay_spin = QDoubleSpinBox(); self.disturbance_delay_spin.setRange(0.5, 300.0); self.disturbance_delay_spin.setSingleStep(0.5)
        self.fine_tune_interval_spin = QDoubleSpinBox(); self.fine_tune_interval_spin.setRange(1.0, 300.0); self.fine_tune_interval_spin.setSingleStep(1.0)
        self.fine_tune_aggr_spin = QDoubleSpinBox(); self.fine_tune_aggr_spin.setRange(0.01, 1.0); self.fine_tune_aggr_spin.setSingleStep(0.01); self.fine_tune_aggr_spin.setDecimals(3)
        self.drift_threshold_spin = QDoubleSpinBox(); self.drift_threshold_spin.setRange(0.01, 0.5); self.drift_threshold_spin.setSingleStep(0.01); self.drift_threshold_spin.setDecimals(3)

        adapt_layout.addRow("Bozucu Etken Eşiği (|Fark| >):", self.disturbance_threshold_spin)
        adapt_layout.addRow("Bozucu Etken Tepki Gecikmesi (sn):", self.disturbance_delay_spin)
        adapt_layout.addRow("Gözlem Süresi (sn):", self.fine_tune_interval_spin)
        adapt_layout.addRow("Normal Ayar Agresifliği (0.01-1.0):", self.fine_tune_aggr_spin)
        adapt_layout.addRow("Drift Düzeltme Eşiği (|Fark| >):", self.drift_threshold_spin)
        
        main_adapt_layout.addWidget(form_widget)
        
        precision_group = QGroupBox("Hassas Ayar (Error < Eşik)")
        precision_layout = QFormLayout(precision_group)
        self.precision_threshold_spin = QDoubleSpinBox(); self.precision_threshold_spin.setRange(0.02, 1.0); self.precision_threshold_spin.setSingleStep(0.01); self.precision_threshold_spin.setDecimals(3)
        self.precision_aggr_spin = QDoubleSpinBox(); self.precision_aggr_spin.setRange(0.001, 0.5); self.precision_aggr_spin.setSingleStep(0.001); self.precision_aggr_spin.setDecimals(3)
        precision_layout.addRow("Hassas Ayar Eşiği:", self.precision_threshold_spin)
        precision_layout.addRow("Hassas Ayar Agresifliği:", self.precision_aggr_spin)
        
        main_adapt_layout.addWidget(precision_group)

        self.countdown_label = QLabel("---")
        font = self.countdown_label.font(); font.setPointSize(14); font.setBold(True); self.countdown_label.setFont(font)
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.countdown_label.setMinimumHeight(40)
        self.countdown_label.setFrameShape(QFrame.Shape.StyledPanel); self.countdown_label.setFrameShadow(QFrame.Shadow.Sunken)
        
        countdown_form_widget = QWidget()
        countdown_layout = QFormLayout(countdown_form_widget)
        countdown_layout.setContentsMargins(0,9,0,0)
        countdown_layout.addRow("Geri Sayım:", self.countdown_label)
        main_adapt_layout.addWidget(countdown_form_widget)

        right_panel_layout.addWidget(self.adapt_group) # GroupBox'ı ana düzene ekle

        right_panel_layout.addStretch()
        top_layout.addWidget(left_panel)
        top_layout.addWidget(right_panel, 1)
        log_group = QGroupBox("Loglar")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit(); self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)
        main_layout.addLayout(top_layout, 0) # Üst panelin dikeyde büyümemesini sağlar
        main_layout.addWidget(log_group, 1) # Log alanına tüm boş alanı verir
    def toggle_adaptation_settings(self):
        is_hidden = self.toggle_adapt_settings_button.isChecked()
        self.adapt_group.setVisible(not is_hidden)
        self.toggle_adapt_settings_button.setText("Göster ▼" if is_hidden else "Gizle ▲")    
    def get_default_fuzzy_settings(self):
        default_valves = [{'name': 'Dolum Vanası', 'min_out': 0.0, 'max_out': 10.0, 'offset': 4},{'name': 'Boşaltma Vanası', 'min_out': 0.0, 'max_out': 10.0, 'offset': 12}]
        default_rules = { 'NH_N': {'Dolum Vanası': 0.0, 'Boşaltma Vanası': 1.0} }
        return {'universe_max':5,'control_range':5.0,'opt_min':0,'opt_max':5,'opt_set':3.3, 'opt_aggr':4.0, 'opt_prec':2.0, 'points':{'NH':[-5,-5,-2.5],'NL':[-3.5,-1.5,-0.1],'Z':[-0.5,0,0.5],'PL':[0.1,1.5,3.5],'PH':[2.5,5,5]}, 'valves': default_valves, 'outputs': default_rules}

    def rebuild_dynamic_ui(self):
        while self.valve_addr_layout.rowCount() > 0: self.valve_addr_layout.removeRow(0)
        while self.valve_output_layout.count(): self.valve_output_layout.takeAt(0).widget().deleteLater()
        self.valve_addr_inputs.clear(); self.valve_output_labels.clear()
        valves = self.fuzzy_settings.get('valves', [])
        self.gain_adaptation_multipliers.clear()
        for i, valve_data in enumerate(valves):
            name = valve_data['name']
            self.gain_adaptation_multipliers[name] = 1.0
            addr_input = QLineEdit(str(valve_data.get('offset', '')))
            addr_input.textChanged.connect(lambda text, n=name: self.update_valve_offset(n, text))
            self.valve_addr_layout.addRow(f"{name} Adresi:", addr_input)
            self.valve_addr_inputs[name] = addr_input
            out_label = QLabel(f"{name}: -")
            out_label.setFrameShape(QFrame.Shape.StyledPanel)
            out_label.setFrameShadow(QFrame.Shadow.Sunken)
            out_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            out_label.setMinimumHeight(40)
            out_label.setStyleSheet("background-color: white;")
            font = out_label.font(); font.setPointSize(12); font.setBold(True); out_label.setFont(font)
            self.valve_output_layout.addWidget(out_label, i // 2, i % 2)
            self.valve_output_labels[name] = out_label
            
    def update_valve_offset(self, valve_name, text):
        try:
            offset = int(text)
            for valve in self.fuzzy_settings['valves']:
                if valve['name'] == valve_name: valve['offset'] = offset; break
        except (ValueError, TypeError): pass

    def load_settings(self):
        self.log("Kaydedilmiş ayarlar yükleniyor...");
        self.ip_input.setText(self.settings.value("plc/ip","192.168.0.1",type=str));self.rack_input.setText(self.settings.value("plc/rack","0",type=str));self.slot_input.setText(self.settings.value("plc/slot","1",type=str));self.db_num_input.setText(self.settings.value("plc/db","1",type=str));self.set_level_addr_input.setText(self.settings.value("addr/set_level","0",type=str));self.levelmeter_addr_input.setText(self.settings.value("addr/levelmeter","8",type=str));self.set_level_value_spin.setValue(self.settings.value("ui/set_level_value",3.3,type=float))
        
        self.disturbance_threshold_spin.setValue(self.settings.value("adaptation/disturbance_threshold", 0.1, type=float))
        self.disturbance_delay_spin.setValue(self.settings.value("adaptation/disturbance_delay", 5.0, type=float))
        self.fine_tune_interval_spin.setValue(self.settings.value("adaptation/fine_tune_interval", 10.0, type=float))
        self.fine_tune_aggr_spin.setValue(self.settings.value("adaptation/fine_tune_aggressiveness", 0.1, type=float))
        self.precision_threshold_spin.setValue(self.settings.value("adaptation/precision_threshold", 0.05, type=float))
        self.precision_aggr_spin.setValue(self.settings.value("adaptation/precision_aggressiveness", 0.01, type=float))
        self.drift_threshold_spin.setValue(self.settings.value("adaptation/drift_threshold", 0.02, type=float))
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.fuzzy_settings = json.load(f)
                    self.log("config.json dosyasından ayarlar başarıyla yüklendi.")
                    self.best_performance_score = self.fuzzy_settings.get("best_performance_score", 0.0)
                    self.best_fuzzy_points = self.fuzzy_settings.get("best_fuzzy_points", None)
                    loaded_multipliers = self.fuzzy_settings.get('gain_multipliers', {})
                    if loaded_multipliers:
                         self.gain_adaptation_multipliers.update(loaded_multipliers)
                         self.is_adapted = True
                    
                    #self.lbl_best_performance.setText(f"En İyi Performans:\n{self.best_performance_score:.2f} E/s" if self.best_performance_score > 0 else "En İyi Performans:\nN/A")
                    return
            except Exception as e:
                self.log(f"config.json okuma hatası: {e}. Varsayılan ayarlar kullanılacak.")
        geometry = self.settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
            
        # Adaptasyon Paneli Görünürlüğü
        is_hidden = self.settings.value("ui/adapt_settings_hidden", False, type=bool)
        self.toggle_adapt_settings_button.setChecked(is_hidden)
        self.toggle_adaptation_settings() # Durumu uygula
        
        if not os.path.exists(self.config_path):
             self.fuzzy_settings = self.get_default_fuzzy_settings()
    
    def save_settings_to_file(self, file_path):
        try:
            temp_settings = copy.deepcopy(self.fuzzy_settings)
            temp_settings['best_performance_score'] = self.best_performance_score
            temp_settings['best_fuzzy_points'] = self.best_fuzzy_points
            temp_settings['gain_multipliers'] = self.gain_adaptation_multipliers
            
            with open(file_path, 'w') as f:
                json.dump(temp_settings, f, indent=4)
            self.log(f"Ayarlar başarıyla {os.path.basename(file_path)} dosyasına kaydedildi.")
            return True
        except Exception as e:
            self.log(f"Ayarları dosyaya kaydetme hatası: {e}")
            QMessageBox.critical(self, "Kayıt Hatası", f"Ayarlar kaydedilemedi:\n{e}")
            return False

    def save_settings_as(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        default_name = f"fuzzy_settings_{timestamp}.json"
        filePath, _ = QFileDialog.getSaveFileName(self, "Ayarları Farklı Kaydet", os.path.join(script_dir, default_name), "JSON Files (*.json)")
        if filePath:
            self.save_settings_to_file(filePath)

    def save_settings(self):
        self.settings.setValue("plc/ip",self.ip_input.text());self.settings.setValue("plc/rack",self.rack_input.text());self.settings.setValue("plc/slot",self.slot_input.text());self.settings.setValue("plc/db",self.db_num_input.text());self.settings.setValue("addr/set_level",self.set_level_addr_input.text());self.settings.setValue("addr/levelmeter",self.levelmeter_addr_input.text());self.settings.setValue("ui/set_level_value",self.set_level_value_spin.value());

        self.settings.setValue("adaptation/disturbance_threshold", self.disturbance_threshold_spin.value())
        self.settings.setValue("adaptation/disturbance_delay", self.disturbance_delay_spin.value())
        self.settings.setValue("adaptation/fine_tune_interval", self.fine_tune_interval_spin.value())
        self.settings.setValue("adaptation/fine_tune_aggressiveness", self.fine_tune_aggr_spin.value())
        self.settings.setValue("adaptation/precision_threshold", self.precision_threshold_spin.value())
        self.settings.setValue("adaptation/precision_aggressiveness", self.precision_aggr_spin.value())
        self.settings.setValue("adaptation/drift_threshold", self.drift_threshold_spin.value())
        self.save_settings_to_file(self.config_path)

    def write_set_level_to_plc(self):
        if not self.plc_manager.is_connected: QMessageBox.warning(self,"Bağlantı Yok","Önce PLC'ye bağlanın."); return
        try:
            self.cancel_disturbance_adaptation() 
            db=int(self.db_num_input.text()); set_addr=int(self.set_level_addr_input.text()); value=self.set_level_value_spin.value()
            level_addr = int(self.levelmeter_addr_input.text())
            current_level = self.plc_manager.read_real(db, level_addr)
            initial_error = value - current_level
            
            if abs(value - self.current_set_level) > 0.001:
                if abs(initial_error) > 0.01:
                    self.adaptation_mode = "SETTLE"
                    self.adaptation_mode_end_time = time.time() + self.INITIAL_SETTLING_TIMEOUT
                    self.log(f"Set değeri değişti. Başlangıç Hatası: {initial_error:.2f}. Oturma ölçümü (SETTLE modu) başladı.")
                else:
                    self.log("Yeni set değeri gönderildi, ancak fark çok küçük. Ayar sıfırlanmadı.")

            self.current_set_level = value
            self.plc_manager.write_real(db,set_addr,value)
            self.log(f"PLC'ye yeni set seviyesi: {value} (DB{db}, Off:{set_addr})")
        except Exception as e: QMessageBox.critical(self,"Hata",f"Set seviyesi gönderilemedi/okunamadı:\n{e}")

    def open_valve_settings(self):
        dialog = ValveSettingsDialog(self.fuzzy_settings.get('valves', []), self)
        if dialog.exec():
            old_names = [v['name'] for v in self.fuzzy_settings['valves']]; new_valves = dialog.valves; new_names = [v['name'] for v in new_valves]
            if old_names != new_names:
                for rule in self.fuzzy_settings['outputs'].values():
                    for old_name, new_name in zip(old_names, new_names):
                        if old_name in rule: rule[new_name] = rule.pop(old_name)
            self.fuzzy_settings['valves'] = new_valves
            self.log("Vana konfigürasyonu güncellendi."); self.rebuild_dynamic_ui(); self.fuzzy_controller = FuzzyPIDController(self.fuzzy_settings); self.save_settings()

    def open_fuzzy_graph_settings(self):
        if self.graph_dialog is None or not self.graph_dialog.isVisible():
            self.graph_dialog = FuzzyGraphSettingsDialog(self.fuzzy_settings, self.settings, self)
            self.graph_dialog.settingsApplied.connect(self.on_graph_settings_applied)
            self.fuzzy_settings_updated.connect(self.graph_dialog.update_from_parent)
            self.graph_dialog.finished.connect(self.on_graph_dialog_finished)
            self.graph_dialog.show()
        else:
            self.graph_dialog.activateWindow()

    def on_graph_dialog_finished(self):
        if self.graph_dialog:
            try:
                self.graph_dialog.settingsApplied.disconnect(self.on_graph_settings_applied)
                self.fuzzy_settings_updated.disconnect(self.graph_dialog.update_from_parent)
            except (TypeError, RuntimeError): pass
        self.graph_dialog = None

    def on_graph_settings_applied(self, new_settings):
        if new_settings != self.fuzzy_settings:
            if self.graph_dialog:
                self.settings.setValue("dialog/opt_min", self.graph_dialog.min_level_spin.value())
                self.settings.setValue("dialog/opt_max", self.graph_dialog.max_level_spin.value())
                self.settings.setValue("dialog/opt_set", self.graph_dialog.set_level_spin.value())
            try:
                test_controller = FuzzyPIDController(new_settings); self.fuzzy_settings = new_settings; self.fuzzy_controller = test_controller
                self.best_fuzzy_points = copy.deepcopy(self.fuzzy_settings['points'])
                #self.best_performance_score = 0.0; self.lbl_best_performance.setText("En İyi Performans:\nN/A")
                self.log("Grafik ayarları güncellendi. Öğrenme hafızası sıfırlandı."); self.save_settings()
                self.static_plot_widget.update_plot(self.fuzzy_settings)
            except Exception as e: self.log(f"Geçersiz ayar: {e}");QMessageBox.warning(self,"Hata",f"Geçersiz ayar: {e}")
            
    def open_rule_settings(self):
        dialog=RuleSettingsDialog(self.fuzzy_settings,self)
        if dialog.exec():
            new_settings=dialog.final_settings
            if new_settings !=self.fuzzy_settings:self.fuzzy_settings=new_settings;self.fuzzy_controller=FuzzyPIDController(self.fuzzy_settings);self.log(f"Kural tablosu güncellendi.");self.save_settings()
    
    def closeEvent(self, event):
        self.save_settings() # Diğer ayarları kaydetmeye devam eder
        
        # --- YENİ: Pencere geometrisini ve UI durumunu kaydet ---
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("ui/adapt_settings_hidden", self.toggle_adapt_settings_button.isChecked())
        
        self.plc_manager.disconnect()
        event.accept()
    
    def toggle_control_loop(self):
        if self.btn_start_stop.isChecked():
            self.stop_countdown()
            self.reset_to_optimized_defaults()
            self.btn_start_stop.setText("Kontrolü Durdur"); self.control_timer.start(500); self.log("Kontrol döngüsü başlatıldı.")
            self.adaptation_mode = "STABLE"
        else: 
            self.control_timer.stop(); self.btn_start_stop.setText("Kontrolü Başlat"); self.log("Kontrol döngüsü durduruldu.")
            self.adaptation_mode = "IDLE"

    def read_and_update_ui(self):
        try:
            db_num = int(self.db_num_input.text()); set_addr = int(self.set_level_addr_input.text()); level_addr = int(self.levelmeter_addr_input.text())
            set_level = self.plc_manager.read_real(db_num, set_addr)
            actual_level = self.plc_manager.read_real(db_num, level_addr)
            
            self.current_set_level = set_level
            self.current_actual_level = actual_level
            self.current_error = set_level - actual_level
            
            active_set_for_log = "N/A"
            if hasattr(self, 'fuzzy_controller'):
                try:
                    active_set_for_log = max({name: fuzz.interp_membership(self.fuzzy_controller.error_antecedent.universe, term.mf, self.current_error) for name, term in self.fuzzy_controller.error_antecedent.terms.items()}.items(), key=lambda item: item[1])[0]
                except (ValueError, IndexError, KeyError): pass
            
            self.lbl_set_level.setText(f"Set Seviye:\n{self.current_set_level:.2f}")
            self.lbl_actual_level.setText(f"Anlık Seviye:\n{self.current_actual_level:.2f}")
            self.lbl_error.setText(f"Fark:\n{self.current_error:.2f} ({active_set_for_log})")
            
            DEADBAND = 0.005
            if abs(self.current_error) < DEADBAND:
                self.lbl_actual_level.setStyleSheet("background-color: #2ecc71; color: white;")
            else:
                self.lbl_actual_level.setStyleSheet("")
        except Exception as e:
            self.log(f"PLC okuma hatası: {e}")
            if self.plc_read_timer.isActive(): self.plc_read_timer.stop()
            if self.plc_manager.is_connected: self.btn_connect.setChecked(False); self.toggle_plc_connection()
            QMessageBox.critical(self,"Okuma Hatası", f"PLC okuma hatası: {e}\nBağlantı kesiliyor.")

    def cancel_disturbance_adaptation(self):
        self.stop_countdown()
        self.adaptation_mode = "STABLE"
        self.frozen_fuzzy_outputs.clear()
        self.log("Kullanıcı müdahalesi: Mevcut bozucu etken/adaptasyon süreci iptal edildi.")        
    
    def run_control_cycle(self):
        try:
            current_error = self.current_error
            db_num = int(self.db_num_input.text())
            dt = self.control_timer.interval() / 1000.0 or 0.5
            delta_error = (current_error - self.last_error)
            DEADBAND = 0.01

            raw_fuzzy_outputs = self.fuzzy_controller.compute(current_error, delta_error / dt) or {}
            log_status = self.adaptation_mode
            valves = self.fuzzy_settings.get('valves', [])

            # --- STATE MACHINE START (STABLE_LOCKED içindeki drift mantığı kaldırıldı) ---
            if self.learning_enabled_checkbox.isChecked():
                if self.adaptation_mode == "SETTLE":
                    if abs(current_error) < DEADBAND or time.time() > self.adaptation_mode_end_time:
                        self.log("Settle modu tamamlandı, tüm adaptasyon ayarları sıfırlanıyor.")
                        self.reset_adaptation_state()
                
                elif self.adaptation_mode in ["STABLE", "STABLE_LOCKED"]:
                    # Bozucu Etken Tespiti (Drift mantığı buradan kaldırıldı, çıkış hesaplamasına taşındı)
                    if abs(current_error) > self.disturbance_threshold_spin.value():
                        log_msg = f"{self.adaptation_mode} modda BOZULMA tespit edildi."
                        if self.is_adapted:
                            log_msg += " Fabrika ayarlarına dönülüyor."
                            self.reset_to_optimized_defaults()
                        self.log(log_msg)
                        self.adaptation_mode = "DISTURBANCE_WAIT"
                        self.adaptation_mode_end_time = time.time() + self.disturbance_delay_spin.value()
                        self.start_countdown(self.disturbance_delay_spin.value())

                elif self.adaptation_mode == "DISTURBANCE_WAIT":
                    if time.time() >= self.adaptation_mode_end_time:
                        self.stop_countdown(); self.adaptation_mode = "POST_DISTURBANCE_OBSERVE"
                        self.adaptation_mode_storage = {'error_history': [], 'start_time': time.time(), 'min_observe_time': 10.0, 'max_observe_time': 40.0, 'stability_threshold': 0.003, 'reversion_outputs': {}, 'baseline_fuzzy_outputs': {}}
                        self.log("Bozucu etken bekleme süresi doldu. Hata stabilize olana kadar GÖZLEM modu başlıyor...")
                
                elif self.adaptation_mode == "POST_DISTURBANCE_OBSERVE":
                    history = self.adaptation_mode_storage['error_history']; history.append(current_error)
                    if len(history) > 20: history.pop(0)
                    time_elapsed = time.time() - self.adaptation_mode_storage['start_time']; is_stable = False
                    if time_elapsed >= self.adaptation_mode_storage['min_observe_time'] and len(history) == 20:
                        stdev = np.std(history)
                        if stdev < self.adaptation_mode_storage['stability_threshold']: is_stable = True
                        elif time_elapsed % 10 < dt: self.log(f"Gözlem Stabil Değil. STDEV: {stdev:.4f}. Bekleniyor...")
                    if is_stable or time_elapsed > self.adaptation_mode_storage['max_observe_time']:
                        if not is_stable: self.log("Gözlem süresi aşıldı, yine de devam ediliyor.")
                        self.log(f"Gözlem tamamlandı. Stabilize olan hata: {current_error:.3f}. Agresif Düzeltme Modu başlatılıyor.")
                        self.adaptation_mode_storage['baseline_fuzzy_outputs'] = copy.deepcopy(raw_fuzzy_outputs)
                        self.log(f"Gözlem sonu ham fuzzy çıktılar saklandı: { {k: f'{v:.2f}' for k,v in self.adaptation_mode_storage['baseline_fuzzy_outputs'].items()} }")
                        target_valve = valves[0]['name'] if current_error > 0 and len(valves) > 0 else (valves[1]['name'] if len(valves) > 1 else None)
                        reversion_outputs = {}
                        if target_valve:
                             for v_conf in valves:
                                 v_name = v_conf['name']; norm_val = raw_fuzzy_outputs.get(v_name, 0.0)
                                 physical_range = v_conf['max_out'] - v_conf['min_out']; reversion_outputs[v_name] = (norm_val * physical_range) + v_conf['min_out']
                        self.adaptation_mode_storage['reversion_outputs'] = reversion_outputs
                        if target_valve:
                            valve_conf = next((v for v in valves if v['name'] == target_valve), None)
                            baseline_output = reversion_outputs.get(target_valve, 0.0); new_target_output = np.clip(baseline_output + (abs(current_error) * 3.0), valve_conf['min_out'], valve_conf['max_out'])
                            self.adaptation_mode_storage['aggressive_target_valve'] = target_valve; self.adaptation_mode_storage['aggressive_output_value'] = new_target_output
                            self.log(f"Agresif Ayar: '{target_valve}' çıkışı {new_target_output:.3f} olarak ayarlandı.")
                        else: self.log("Agresif ayar için hedef vana bulunamadı. İnce ayara geçiliyor."); self.adaptation_mode = "FINE_TUNE"
                        self.adaptation_mode = "AGGRESSIVE_CORRECTION"
                
                elif self.adaptation_mode == "AGGRESSIVE_CORRECTION":
                    if abs(current_error) <= 0.05:
                        self.adaptation_mode = "PRECISION_OBSERVE"; self.adaptation_mode_end_time = time.time() + 10.0
                        self.log("Hedef hata değerine ulaşıldı. Vana çıkışları gözlem değerine geri çekildi."); self.log("10 saniyelik Hassas Gözlem moduna geçiliyor.")

                elif self.adaptation_mode == "PRECISION_OBSERVE":
                    if time.time() >= self.adaptation_mode_end_time:
                        self.log("Hassas gözlem tamamlandı. Standart İnce Ayar moduna geçiliyor."); self.adaptation_mode = "FINE_TUNE"; self.is_in_fine_tune_observation = False
                        self.frozen_fuzzy_outputs = self.adaptation_mode_storage.get('baseline_fuzzy_outputs', copy.deepcopy(raw_fuzzy_outputs))
                        self.log(f"Temel çıkışlar GÖZLEM SONU değerlerine göre donduruldu: { {k: f'{v:.2f}' for k,v in self.frozen_fuzzy_outputs.items()} }")

                elif self.adaptation_mode == "FINE_TUNE":
                    if abs(current_error) < DEADBAND:
                        self.log("İnce Ayar başarılı! Hata DEADBAND içine girdi. Son kararlı çıkışlar kilitleniyor.")
                        self.locked_stable_outputs.clear()
                        proactive_reduction = 0.04
                        dominant_valve = self.last_adaptation_info.get('valve')
                        if dominant_valve:
                            self.adaptation_mode_storage['dominant_correction_valve'] = dominant_valve
                            self.log(f"Dominant vana '{dominant_valve}' olarak ayarlandı.")
                        for v_conf in valves:
                            v_name = v_conf['name']; norm_val = self.frozen_fuzzy_outputs.get(v_name, 0.0); gain = self.gain_adaptation_multipliers.get(v_name, 1.0)
                            final_locked_value = norm_val * gain
                            if v_name == dominant_valve:
                                self.log(f"'{v_name}' için proaktif azaltma uygulanıyor. Orijinal: {final_locked_value:.4f}")
                                final_locked_value = max(0.0, final_locked_value - proactive_reduction)
                                self.log(f"Yeni kilit değeri: {final_locked_value:.4f}")
                            self.locked_stable_outputs[v_name] = final_locked_value
                        self.is_adapted = True; self.adaptation_mode = "STABLE_LOCKED"; self.frozen_fuzzy_outputs.clear()
                    
                    elif self.is_in_fine_tune_observation:
                        if time.time() >= self.adaptation_mode_end_time: self._evaluate_observation_and_decide_next_step(current_error)
                    else:
                        if not self.frozen_fuzzy_outputs:
                             self.frozen_fuzzy_outputs = copy.deepcopy(raw_fuzzy_outputs)
                             self.log(f"İnce Ayar Modu Başladı. Temel çıkışlar donduruldu: { {k: f'{v:.2f}' for k,v in self.frozen_fuzzy_outputs.items()} }")
                        self._perform_adaptation_step(current_error, delta_error, dt)

            # --- VANA ÇIKIŞ HESAPLAMA (DEĞİŞİKLİKLER BURADA) ---
            log_msg_parts = []
            for valve_conf in valves:
                valve_name = valve_conf['name']; physical_value = 0.0
                current_gain = self.gain_adaptation_multipliers.get(valve_name, 1.0)

                if self.adaptation_mode == "AGGRESSIVE_CORRECTION":
                    physical_value = self.adaptation_mode_storage.get('aggressive_output_value', valve_conf['min_out']) if valve_name == self.adaptation_mode_storage.get('aggressive_target_valve') else valve_conf['min_out']
                
                elif self.adaptation_mode == "PRECISION_OBSERVE":
                    physical_value = self.adaptation_mode_storage.get('reversion_outputs', {}).get(valve_name, valve_conf['min_out'])
                
                # --- YENİ MANTIK BURADA BAŞLIYOR ---
                elif self.adaptation_mode == "STABLE_LOCKED":
                    log_status = "STABLE_LOCKED" # Varsayılan durum
                    base_norm_val = self.locked_stable_outputs.get(valve_name, 0.0)
                    final_norm_val = base_norm_val

                    # STABLE_LOCKED için Nudge Mantığı
                    if abs(current_error) > 0.001:
                        log_status = "LOCKED_NUDGE" # Log durumu güncellendi
                        nudge_amount = 0.1
                        fill_valve_name = valves[0]['name'] if len(valves) > 0 else None
                        drain_valve_name = valves[1]['name'] if len(valves) > 1 else None

                        # Hata pozitifse (dolum gerek), sadece dolum vanasını dürt
                        if current_error > 0 and valve_name == fill_valve_name:
                            final_norm_val = base_norm_val + nudge_amount
                        # Hata negatifse (boşaltma gerek), sadece boşaltma vanasını dürt
                        elif current_error < 0 and valve_name == drain_valve_name:
                             final_norm_val = base_norm_val + nudge_amount
                    
                    final_norm_val = np.clip(final_norm_val, 0.0, 1.0)
                    physical_range = valve_conf['max_out'] - valve_conf['min_out']
                    physical_value = (final_norm_val * physical_range) + valve_conf['min_out']
                
                else: # ACTIVE FUZZY CONTROL (STABLE, SETTLE, FINE_TUNE, vb.)
                    normalized_value = raw_fuzzy_outputs.get(valve_name, 0.0)
                    output_to_use = self.frozen_fuzzy_outputs.get(valve_name, normalized_value) if self.adaptation_mode == "FINE_TUNE" else normalized_value
                    final_normalized_value = max(0.0, min(1.0, output_to_use * current_gain))

                    if self.adaptation_mode == "STABLE" and not self.is_adapted:
                        log_status = "STABLE_NUDGE"
                        fill_valve_name = valves[0]['name'] if len(valves) > 0 else None
                        drain_valve_name = valves[1]['name'] if len(valves) > 1 else None
                        if abs(current_error) > 0.001:
                            if current_error > 0: final_normalized_value = 0.01 if valve_name == fill_valve_name else 0.0
                            else: final_normalized_value = 0.01 if valve_name == drain_valve_name else 0.0
                        else: final_normalized_value = 0.0
                    
                    elif self.adaptation_mode not in ["STABLE", "STABLE_LOCKED"]:
                        fill_valve_name = valves[0]['name'] if len(valves) > 0 else None
                        drain_valve_name = valves[1]['name'] if len(valves) > 1 else None
                        if current_error > 0 and valve_name == drain_valve_name: final_normalized_value = 0.0
                        elif current_error < 0 and valve_name == fill_valve_name: final_normalized_value = 0.0

                    physical_range = valve_conf['max_out'] - valve_conf['min_out']
                    physical_value = (final_normalized_value * physical_range) + valve_conf['min_out']
                
                addr_str = self.valve_addr_inputs.get(valve_name)
                if addr_str and addr_str.text(): self.plc_manager.write_real(int(db_num), int(addr_str.text()), physical_value)
                self.valve_output_labels[valve_name].setText(f"{valve_name}\n{physical_value:.2f}")
                log_msg_parts.append(f"{valve_name[:1]}:{physical_value:.2f}(G:{current_gain:.2f})")
            
            self.last_error = current_error
            self.log(f"E:{current_error:.2f}, dE:{delta_error/dt:.2f} [{log_status}] -> {', '.join(log_msg_parts)}")
        
        except Exception as e:
            logging.exception("Kontrol döngüsünde kritik hata oluştu:")
            self.log(f"Döngü hatası: {e}")
            if self.control_timer.isActive():self.btn_start_stop.setChecked(False);self.toggle_control_loop()
            if self.plc_manager.is_connected:self.btn_connect.setChecked(False);self.toggle_plc_connection()

    def _perform_adaptation_step(self, current_error, delta_error, dt):
        if not self.frozen_fuzzy_outputs:
            self.frozen_fuzzy_outputs = self.fuzzy_controller.compute(current_error, delta_error / dt) or {}
            self.log(f"İnce Ayar Modu Başladı. Temel çıkışlar donduruldu: { {k: f'{v:.2f}' for k,v in self.frozen_fuzzy_outputs.items()} }")
        
        if self.last_adaptation_info.get('reverting', False):
            self.log("Kalıcı Geri Alma döngüsü aktif. Yeni adım atlanıyor, geri almaya devam ediliyor.")
            self._revert_last_adaptation(is_permanent_revert=True)
            return

        error_abs = abs(current_error)
        step_size = 0.0
        adapt_type_log = ""
        
        observation_duration = 10.0 if error_abs < 0.3 else self.fine_tune_interval_spin.value()
        error_trend = delta_error / dt if dt > 0 else 0.0
        
        if error_abs < self.precision_threshold_spin.value():
            adapt_type_log = "Hassas (İniş Modu)"
            damping_factor = self.precision_aggr_spin.value() * 10
            p_adjustment = current_error * 0.1
            d_adjustment = -error_trend * damping_factor
            control_value = p_adjustment + d_adjustment
            adjustment = np.clip(control_value, -0.05, 0.05)
        else:
            adapt_type_log = "Normal (Trend Tabanlı)"
            damping_factor = 0.5 
            if current_error > 0:
                step_size = (error_abs + (error_trend * damping_factor)) * self.fine_tune_aggr_spin.value()
            else:
                step_size = (error_abs - (error_trend * damping_factor)) * self.fine_tune_aggr_spin.value()
            adjustment = np.clip(abs(step_size), 0.001, 0.1)
        
        target_valve = None
        valves = self.fuzzy_settings.get('valves', [])
        if current_error > 0: target_valve = valves[0]['name'] if len(valves) > 0 else None
        else: target_valve = valves[1]['name'] if len(valves) > 1 else None

        if target_valve:
            final_adjustment = adjustment if adapt_type_log.startswith("Hassas") or current_error > 0 else -adjustment
            self.gain_adaptation_multipliers[target_valve] += final_adjustment
            self.last_adaptation_info = {'type': 'gain_adjust', 'valve': target_valve, 'amount': final_adjustment, 'reverting': False}
            self.log(f"İnce Ayar ({adapt_type_log}): '{target_valve}' kazancı -> {self.gain_adaptation_multipliers[target_valve]:.3f} (Adım: {final_adjustment:+.3f})")
        
        self.is_in_fine_tune_observation = True
        self.adaptation_mode_end_time = time.time() + (1.0 if adapt_type_log.startswith("Hassas") else observation_duration)
        self.adaptation_mode_storage['observation_initial_error'] = current_error
        self.log(f"Adaptasyon adımı atıldı. {self.adaptation_mode_end_time - time.time():.1f}sn boyunca İnce Ayar GÖZLEM moduna geçiliyor.")

    def _evaluate_observation_and_decide_next_step(self, current_error):
        initial_error = self.adaptation_mode_storage.get('observation_initial_error', 0.0)
        progress = abs(initial_error) - abs(current_error)
        self.log(f"İnce Ayar Gözlem tamamlandı. Başlangıç E: {initial_error:.3f}, Bitiş E: {current_error:.3f}. İlerleme: {progress:.3f}")
        self.is_in_fine_tune_observation = False
        
        has_overshoot = np.sign(current_error) != np.sign(initial_error) and abs(current_error) > 0.01

        if self.last_adaptation_info.get('reverting', False):
            if has_overshoot:
                self.log("Kalıcı Geri Alma devam ediyor...")
                return
            else:
                self.log("Kalıcı Geri Alma modu overshoot düzeldiği için sonlandırıldı.")
                self.last_adaptation_info['reverting'] = False
        
        if has_overshoot and not self.last_adaptation_info.get('reverting', False):
            self.log("OVERSHOOT tespit edildi! Geri Alma başlatılıyor.")
            is_permanent = abs(initial_error) < self.precision_threshold_spin.value()
            if is_permanent:
                self.log("Hassas modda overshoot, kalıcı geri alma döngüsü başlatılıyor.")
                self.last_adaptation_info['reverting'] = True
            self._revert_last_adaptation(is_permanent_revert=is_permanent)

    def _revert_last_adaptation(self, is_permanent_revert=False):
        if not self.last_adaptation_info:
            self.log("Geri alınacak bir adaptasyon adımı bulunamadı."); return

        reversal_factor = 1.0 if is_permanent_revert else 0.5 
        info = self.last_adaptation_info.copy() 
        amount_to_revert = info.get('amount', 0.0) * reversal_factor
        revert_log_prefix = "Kalıcı Geri Alma" if is_permanent_revert else "Geri Alma"
        valve_name = info.get('valve')
        if valve_name:
            current_gain = self.gain_adaptation_multipliers[valve_name]
            self.gain_adaptation_multipliers[valve_name] = max(1.0, current_gain - amount_to_revert)
            self.log(f"{revert_log_prefix} (Kazanç): '{valve_name}' kazancı -> {self.gain_adaptation_multipliers[valve_name]:.3f}")
        
        if not is_permanent_revert:
            self.last_adaptation_info = {}
        else:
            self.last_adaptation_info['amount'] = -amount_to_revert 
        
        error_abs = abs(self.current_error)
        self.is_in_fine_tune_observation = True
        observation_duration = 10.0 if error_abs < 0.3 else self.fine_tune_interval_spin.value()
        self.adaptation_mode_end_time = time.time() + observation_duration
        self.adaptation_mode_storage['observation_initial_error'] = self.current_error
        self.log(f"Geri alma sonrası {observation_duration:.1f}sn GÖZLEM moduna geçiliyor.")

    def start_countdown(self, delay_seconds):
        self.disturbance_countdown_timer.start(50)

    def stop_countdown(self):
        self.disturbance_countdown_timer.stop()
        self.countdown_label.setText("---"); self.countdown_label.setStyleSheet("")

    def update_countdown_label(self):
        if self.adaptation_mode != "DISTURBANCE_WAIT": 
            self.stop_countdown()
            return
        remaining = self.adaptation_mode_end_time - time.time()
        if remaining <= 0: self.countdown_label.setText("00:00")
        else:
            seconds = int(remaining); milliseconds = int((remaining - seconds) * 100)
            self.countdown_label.setText(f"{seconds:02d}:{milliseconds:02d}")
            self.countdown_label.setStyleSheet("background-color: #f39c12; color: white;")
        
    def reset_adaptation_state(self):
        self.log("Tam adaptasyon sıfırlaması yapılıyor. STABLE moda geçiliyor.")
        self.adaptation_mode = "STABLE"
        self.is_adapted = False
        self.is_in_fine_tune_observation = False
        self.adaptation_mode_end_time = 0.0
        
        # Dominant vana bilgisini de temizle
        if 'dominant_correction_valve' in self.adaptation_mode_storage:
            self.adaptation_mode_storage.pop('dominant_correction_valve')
            
        self.last_adaptation_info = {}
        self.locked_stable_outputs.clear()
        self.frozen_fuzzy_outputs.clear()
        self.stop_countdown()
        for key in self.gain_adaptation_multipliers: self.gain_adaptation_multipliers[key] = 1.0
        
        self.drift_adjustment_values.clear()
        self.drift_correction_timer = 0.0
    def reset_to_optimized_defaults(self):
        self.log("Fabrika ayarlarına (hesaplanmış optimum) dönülüyor.")
        self.reset_adaptation_state()

        min_l = self.settings.value("dialog/opt_min", self.fuzzy_settings.get('opt_min', 0), type=float)
        max_l = self.settings.value("dialog/opt_max", self.fuzzy_settings.get('opt_max', 5), type=float)
        set_l = self.settings.value("dialog/opt_set", self.fuzzy_settings.get('opt_set', 3.3), type=float)
        agg_factor = self.fuzzy_settings.get('opt_aggr', 4.0); prec_factor = self.fuzzy_settings.get('opt_prec', 2.0)
        agg_multiplier = 1.0 / agg_factor; prec_multiplier = 1.0 / prec_factor
        total_range = max_l - min_l if max_l > min_l else 1
        max_pos_error = set_l - min_l; max_neg_error = set_l - max_l
        z_width = (total_range * 0.05) * prec_multiplier
        pl_peak = (max_pos_error * 0.4) * agg_multiplier; pl_end = (max_pos_error * 0.8) * agg_multiplier
        ph_start = (max_pos_error * 0.7) * agg_multiplier; nl_peak = (max_neg_error * 0.4) * agg_multiplier
        nl_end = (max_neg_error * 0.8) * agg_multiplier; nh_start = (max_neg_error * 0.7) * agg_multiplier
        pl_peak = max(pl_peak, z_width + 0.01); nl_peak = min(nl_peak, -z_width - 0.01)
        new_points = {
            'Z': [-z_width, 0, z_width], 'PL': [z_width, pl_peak, pl_end], 'PH': [ph_start, max_pos_error, max_pos_error],
            'NL': [nl_end, nl_peak, -z_width], 'NH': [max_neg_error, max_neg_error, nh_start]
        }
        self.fuzzy_settings['points'] = new_points
        self.best_fuzzy_points = copy.deepcopy(new_points)
        valves = self.fuzzy_settings.get('valves', []); fill_valve = valves[0]['name'] if len(valves) > 0 else None; drain_valve = valves[1]['name'] if len(valves) > 1 else None
        raw_rules = {
            'PH_P':{'fill':1.0,'drain':0},'PH_Z':{'fill':0.9,'drain':0},'PH_N':{'fill':0.7,'drain':0},
            'PL_P':{'fill':0.6,'drain':0},'PL_Z':{'fill':0.3,'drain':0},'PL_N':{'fill':0.1,'drain':0},
            'Z_P':{'fill':0.15,'drain':0},'Z_Z':{'fill':0,'drain':0},'Z_N':{'fill':0,'drain':0.15},
            'NL_P':{'fill':0,'drain':0.1},'NL_Z':{'fill':0,'drain':0.3},'NL_N':{'fill':0,'drain':0.6},
            'NH_P':{'fill':0,'drain':0.7},'NH_Z':{'fill':0,'drain':0.9},'NH_N':{'fill':1.0,'drain':1.0},
        }
        optimized_rules = {}
        for key, vals in raw_rules.items():
            rule_entry = {}
            if fill_valve: rule_entry[fill_valve] = vals['fill']
            if drain_valve: rule_entry[drain_valve] = vals['drain']
            optimized_rules[key] = rule_entry
        self.fuzzy_settings['outputs'] = optimized_rules
        self.fuzzy_controller = FuzzyPIDController(self.fuzzy_settings)
        if self.graph_dialog: self.fuzzy_settings_updated.emit(self.fuzzy_settings)
        self.static_plot_widget.update_plot(self.fuzzy_settings)
        self.save_settings()

    def log(self, m):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_output.append(f"[{timestamp}] {m}")
        logging.info(m)

    def toggle_plc_connection(self):
        if self.btn_connect.isChecked():
            try:ip=self.ip_input.text();r=int(self.rack_input.text());s=int(self.slot_input.text())
            except ValueError:QMessageBox.critical(self,"Hata","Rack/Slot sayısal olmalı.");self.btn_connect.setChecked(False);return
            self.log(f"PLC'ye bağlanılıyor: {ip}...");suc,msg=self.plc_manager.connect(ip,r,s)
            if suc:
                self.btn_connect.setText("PLC Bağlı (Kes)");self.btn_connect.setStyleSheet("background-color: #27ae60; color: white;");self.btn_start_stop.setEnabled(True);self.log(msg)
                self.plc_read_timer.start(1000)
            else:
                QMessageBox.critical(self,"Bağlantı Hatası",msg);self.btn_connect.setChecked(False);self.log(f"Bağlantı başarısız: {msg}")
        else:
            if self.control_timer.isActive():self.btn_start_stop.setChecked(False);self.toggle_control_loop()
            self.plc_read_timer.stop()
            self.plc_manager.disconnect();self.btn_connect.setText("PLC'ye Bağlan");self.btn_connect.setStyleSheet("");self.btn_start_stop.setEnabled(False);self.log("PLC bağlantısı kesildi.")
            self.lbl_set_level.setText("Set Seviye: -"); self.lbl_actual_level.setText("Anlık Seviye: -"); self.lbl_error.setText("Fark: -")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())