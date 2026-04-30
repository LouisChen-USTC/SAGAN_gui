"""Mouse drag handler for interactive parameter adjustment."""
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, Qt

from .model_registry import MODELS, get_param_role
from sagan.constants import ls_km


def _get_line_anchors(model, model_name):
    """Compute the three anchor positions for a line/absorption model.

    Returns list of (x, y, role) tuples: [(peak_x, peak_y, 'peak'),
    (left_x, left_y, 'sigma'), (right_x, right_y, 'sigma')]
    or None if not applicable.
    """
    info = MODELS.get(model_name)
    if info is None:
        return None

    category = info['category']
    if category not in ('line', 'absorption'):
        return None

    wavec = None
    dv = 0.0
    sigma = None
    amplitude = None
    tau_0 = None
    Cf = 1.0

    for pname in model.param_names:
        val = getattr(model, pname).value
        if pname == 'wavec':
            wavec = val
        elif pname == 'dv':
            dv = val
        elif pname == 'sigma':
            sigma = val
        elif pname == 'w':
            sigma = val
        elif pname == 'amplitude':
            amplitude = val
        elif pname == 'tau_0':
            tau_0 = val
        elif pname == 'log_tau0':
            tau_0 = 10 ** val
        elif pname == 'Cf':
            Cf = val

    if wavec is None:
        return None

    center_x = wavec * (1.0 + dv / ls_km)

    if category == 'line' and amplitude is not None:
        sigma = sigma if sigma is not None else 200.0
        left_x = wavec * (1.0 + (dv - sigma) / ls_km)
        right_x = wavec * (1.0 + (dv + sigma) / ls_km)
        half_val = amplitude * np.exp(-0.5)
        return [
            (center_x, amplitude, 'peak'),
            (left_x, half_val, 'sigma'),
            (right_x, half_val, 'sigma'),
        ]

    if category == 'absorption' and tau_0 is not None:
        sigma = sigma if sigma is not None else 200.0
        left_x = wavec * (1.0 + (dv - sigma) / ls_km)
        right_x = wavec * (1.0 + (dv + sigma) / ls_km)
        f_center = 1.0 - Cf + Cf * np.exp(-tau_0)
        f_half = 1.0 - Cf + Cf * np.exp(-tau_0 * np.exp(-0.5))
        return [
            (center_x, f_center, 'peak'),
            (left_x, f_half, 'sigma'),
            (right_x, f_half, 'sigma'),
        ]

    return None


class DragHandler(QObject):
    """Handle mouse drag interactions on the matplotlib canvas."""

    parameter_changed = pyqtSignal(int, str, float)
    drag_started = pyqtSignal(int)
    drag_ended = pyqtSignal()

    HIT_RADIUS_PX = 18

    def __init__(self, canvas_widget, parent=None):
        super().__init__(parent)
        self.canvas_widget = canvas_widget
        self.mpl_canvas = canvas_widget.canvas
        self.ax = canvas_widget.ax

        self._dragging = False
        self._drag_index = -1
        self._drag_mode = None
        self._press_x = None
        self._press_y = None
        self._original_params = {}
        self._components = []

        self.mpl_canvas.mpl_connect('button_press_event', self._on_press)
        self.mpl_canvas.mpl_connect('motion_notify_event', self._on_motion)
        self.mpl_canvas.mpl_connect('button_release_event', self._on_release)

    def set_components(self, components):
        self._components = components

    def _find_hit(self, mx, my):
        """Find what the mouse hit: anchor point, line body, or nothing.

        Returns (component_index, mode) where mode is
        'peak', 'sigma', or 'body'. Returns (-1, None) if nothing hit.
        """
        if mx is None or my is None:
            return -1, None

        best_dist = self.HIT_RADIUS_PX
        best_idx = -1
        best_mode = None

        for i, comp in enumerate(self._components):
            if not comp['visible']:
                continue
            model_name = comp['model_name']
            info = MODELS.get(model_name)
            if info is None or info['category'] not in ('line', 'absorption'):
                continue

            model = comp['model']
            anchors = _get_line_anchors(model, model_name)
            if anchors is None:
                continue

            px_mouse = self.ax.transData.transform([(mx, my)])[0]

            for ax_pos, ay_pos, role in anchors:
                px_anchor = self.ax.transData.transform([(ax_pos, ay_pos)])[0]
                dist = np.sqrt((px_anchor[0] - px_mouse[0]) ** 2 +
                               (px_anchor[1] - px_mouse[1]) ** 2)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i
                    best_mode = role

            if best_mode is not None:
                continue

            wavec = None
            sigma_val = None
            for pname in model.param_names:
                if pname == 'wavec':
                    wavec = getattr(model, pname).value
                elif pname in ('sigma', 'w'):
                    sigma_val = getattr(model, pname).value

            if wavec is not None and sigma_val is not None:
                dv_val = 0.0
                for pname in model.param_names:
                    if pname == 'dv':
                        dv_val = getattr(model, pname).value
                center = wavec * (1.0 + dv_val / ls_km)
                half_range = wavec * sigma_val / ls_km * 2.0

                if center - half_range <= mx <= center + half_range:
                    try:
                        model_y = model(np.array([mx]))[0]
                    except Exception:
                        model_y = 0.0
                    if abs(my - model_y) < (self.ax.get_ylim()[1] - self.ax.get_ylim()[0]) * 0.15:
                        body_dist = abs(my - model_y)
                        px_body = self.ax.transData.transform([(mx, model_y)])[0]
                        pixel_dist = abs(px_body[1] - px_mouse[1])
                        if pixel_dist < self.HIT_RADIUS_PX * 1.5:
                            best_idx = i
                            best_mode = 'body'
                            best_dist = pixel_dist

        return best_idx, best_mode

    def _is_over_line(self, mx, my):
        """Check if the mouse is hovering over any interactive line."""
        if mx is None or my is None:
            return False
        for comp in self._components:
            if not comp['visible']:
                continue
            model_name = comp['model_name']
            info = MODELS.get(model_name)
            if info is None or info['category'] not in ('line', 'absorption'):
                continue

            model = comp['model']
            anchors = _get_line_anchors(model, model_name)
            if anchors is None:
                continue

            px_mouse = self.ax.transData.transform([(mx, my)])[0]
            for ax_pos, ay_pos, _ in anchors:
                px_anchor = self.ax.transData.transform([(ax_pos, ay_pos)])[0]
                dist = np.sqrt((px_anchor[0] - px_mouse[0]) ** 2 +
                               (px_anchor[1] - px_mouse[1]) ** 2)
                if dist < self.HIT_RADIUS_PX:
                    return True

            wavec = None
            sigma_val = None
            for pname in model.param_names:
                if pname == 'wavec':
                    wavec = getattr(model, pname).value
                elif pname in ('sigma', 'w'):
                    sigma_val = getattr(model, pname).value
            if wavec is not None and sigma_val is not None:
                dv_val = 0.0
                for pname in model.param_names:
                    if pname == 'dv':
                        dv_val = getattr(model, pname).value
                center = wavec * (1.0 + dv_val / ls_km)
                half_range = wavec * sigma_val / ls_km * 2.0
                if center - half_range <= mx <= center + half_range:
                    try:
                        model_y = model(np.array([mx]))[0]
                    except Exception:
                        continue
                    px_model = self.ax.transData.transform([(mx, model_y)])[0]
                    if abs(px_model[1] - px_mouse[1]) < self.HIT_RADIUS_PX * 1.5:
                        return True
        return False

    def _on_press(self, event):
        if event.inaxes != self.ax or event.button != 1:
            return
        toolbar = self.canvas_widget.toolbar
        if toolbar.mode != '':
            return

        mx, my = event.xdata, event.ydata
        idx, mode = self._find_hit(mx, my)

        if idx >= 0:
            self._dragging = True
            self._drag_index = idx
            self._drag_mode = mode
            self._press_x = mx
            self._press_y = my

            comp = self._components[idx]
            model = comp['model']
            self._original_params = {}
            for pname in model.param_names:
                self._original_params[pname] = getattr(model, pname).value

            self.drag_started.emit(idx)

    def _on_motion(self, event):
        if event.inaxes != self.ax:
            self.mpl_canvas.unsetCursor()
            return

        mx, my = event.xdata, event.ydata

        if not self._dragging:
            if self._is_over_line(mx, my):
                self.mpl_canvas.setCursor(Qt.CrossCursor)
            else:
                self.mpl_canvas.unsetCursor()
            return

        if mx is None or my is None:
            return

        dx = mx - self._press_x
        dy = my - self._press_y

        comp = self._components[self._drag_index]
        model = comp['model']
        model_name = comp['model_name']
        info = MODELS.get(model_name)

        if self._drag_mode == 'peak':
            if abs(dy) > 0:
                pname_amp = self._find_param_by_role(model, model_name, 'amplitude')
                if pname_amp:
                    new_val = self._original_params[pname_amp] + dy
                    self.parameter_changed.emit(self._drag_index, pname_amp, new_val)

        elif self._drag_mode == 'sigma':
            if abs(dx) > 0:
                wavec_val = self._original_params.get('wavec', 0)
                if wavec_val and wavec_val > 0:
                    pname_sigma = self._find_param_by_role(model, model_name, 'sigma')
                    if pname_sigma:
                        sigma_new = self._original_params[pname_sigma] + dx / wavec_val * ls_km
                        sigma_new = max(sigma_new, 20.0)
                        self.parameter_changed.emit(self._drag_index, pname_sigma, sigma_new)

        elif self._drag_mode == 'body':
            if abs(dx) > 0:
                wavec_val = self._original_params.get('wavec', 0)
                if wavec_val and wavec_val > 0:
                    pname_dv = self._find_param_by_role(model, model_name, 'dv')
                    if pname_dv:
                        dv_new = self._original_params[pname_dv] + dx / wavec_val * ls_km
                        self.parameter_changed.emit(self._drag_index, pname_dv, dv_new)

    def _on_release(self, event):
        if self._dragging:
            self._dragging = False
            self._drag_index = -1
            self._drag_mode = None
            self._original_params = {}
            self.drag_ended.emit()

    def _find_param_by_role(self, model, model_name, role):
        for pname in model.param_names:
            r = get_param_role(model_name, pname)
            if r == role:
                return pname
        return None
