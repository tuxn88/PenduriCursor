import ctypes

myappid = "penduricursor.app.1.0"
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

import json
import os
import math
import random
import ctypes
import shutil
import threading
import sys
import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox
import customtkinter as ctk
from pynput import mouse
from PIL import Image, ImageTk, ImageDraw
import pystray

# Ativar High DPI no Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Definir visual escuro e paleta personalizada (#a0a0dc)
ctk.set_appearance_mode("Dark")

# Definição de Diretórios Base do App (Garante funcionamento sem erro de permissão)
def obter_diretorio_app():
    appdata = os.getenv("APPDATA")
    if appdata:
        base = os.path.join(appdata, "PenduriCursor")
    else:
        base = os.path.join(os.path.expanduser("~"), ".penduricursor")
    
    try:
        os.makedirs(base, exist_ok=True)
        os.makedirs(os.path.join(base, "Presets"), exist_ok=True)
        return base
    except Exception:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PenduriCursorData")
        os.makedirs(base, exist_ok=True)
        os.makedirs(os.path.join(base, "Presets"), exist_ok=True)
        return base

BASE_APP_DIR = obter_diretorio_app()
PRESETS_DIR = os.path.join(BASE_APP_DIR, "Presets")
CONFIG_FILE = os.path.join(BASE_APP_DIR, "config_penduricursor.json")


class OverlayPenduricalho:
    def __init__(self, app_principal):
        self.app = app_principal
        self.root = None
        self.canvas = None
        self.listener = None
        self.ativo = False
        
        # Física
        self.mouse_x, self.mouse_y = 0, 0
        self.last_mouse_x, self.last_mouse_y = 0, 0
        self.item_x, self.item_y = 0.0, 0.0
        self.vx, self.vy = 0.0, 0.0
        
        # Imagens e GIF
        self.frames_idle = []
        self.frames_moving = []
        self.part_imgs = []
        self.anim_tick = 0
        self.moving_cooldown = 0
        
        # Rastro e Partículas
        self.rastro_pontos = []
        self.particulas = []
        self.frame_count = 0

    def obter_dimensoes_tela(self):
        SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
        SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
        user32 = ctypes.windll.user32
        vx, vy = user32.GetSystemMetrics(SM_XVIRTUALSCREEN), user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw, vh = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN), user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        if vw == 0 or vh == 0:
            vw, vh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            vx, vy = 0, 0
        return vx, vy, vw, vh

    def iniciar(self):
        if self.ativo: return
        self.ativo = True
        self.root = tk.Toplevel()
        self.root.title("PenduriCursor Overlay")
        
        vx, vy, vw, vh = self.obter_dimensoes_tela()
        self.offset_x, self.offset_y = vx, vy

        self.root.geometry(f"{vw}x{vh}+{vx}+{vy}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        self.trans_color = '#000001'
        self.root.config(bg=self.trans_color)
        self.root.wm_attributes('-transparentcolor', self.trans_color)
        
        self.canvas = tk.Canvas(self.root, width=vw, height=vh, bg=self.trans_color, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.ativar_click_through_perfeito()
        self.carregar_imagens()

        self.mouse_x, self.mouse_y = vw // 2, vh // 2
        self.item_x, self.item_y = float(self.mouse_x), float(self.mouse_y + self.app.tamanho_corda.get())
        self.rastro_pontos = []

        self.listener = mouse.Listener(on_move=self.on_move)
        self.listener.start()
        self.atualizar_fisica()

    def ativar_click_through_perfeito(self):
        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT, WS_EX_LAYERED = 0x00000020, 0x00080000
        WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = 0x08000000, 0x00000080
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)

    def carregar_gif(self, caminho, tamanho, flip_x, flip_y):
        frames = []
        if caminho and os.path.exists(caminho):
            try:
                img = Image.open(caminho)
                for i in range(getattr(img, 'n_frames', 1)):
                    img.seek(i)
                    f = img.convert("RGBA").resize((tamanho, tamanho), Image.Resampling.LANCZOS)
                    if flip_x: f = f.transpose(Image.FLIP_LEFT_RIGHT)
                    if flip_y: f = f.transpose(Image.FLIP_TOP_BOTTOM)
                    frames.append(f)
            except Exception: pass
        return frames

    def carregar_imagens(self):
        t = int(self.app.tamanho_item.get())
        fx, fy = self.app.flip_x.get(), self.app.flip_y.get()
        self.frames_idle = self.carregar_gif(self.app.caminho_idle, t, fx, fy)
        self.frames_moving = self.carregar_gif(self.app.caminho_moving, t, fx, fy)
        
        self.part_imgs = []
        if self.app.part_img and os.path.exists(self.app.part_img):
            try:
                base_img = Image.open(self.app.part_img).convert("RGBA")
                base_t = int(self.app.part_tamanho.get())
                variar = self.app.part_var_tam.get()
                
                escalas = [0.5, 0.75, 1.0, 1.25, 1.5] if variar else [1.0]
                for s in escalas:
                    sz = max(2, int(base_t * s))
                    img_p = base_img.resize((sz, sz), Image.Resampling.LANCZOS)
                    self.part_imgs.append(ImageTk.PhotoImage(img_p))
            except Exception: pass

    def on_move(self, x, y):
        self.mouse_x, self.mouse_y = x - self.offset_x, y - self.offset_y

    def obter_frame_renderizado(self, frames_list, frame_idx, angulo_graus):
        if not frames_list: return None
        idx = frame_idx % len(frames_list)
        angulo_int = int(round(angulo_graus)) % 360
        
        if getattr(self, '_last_rot_key', None) == (idx, angulo_int) and getattr(self, '_last_rot_tk', None):
            return self._last_rot_tk
            
        img_original = frames_list[idx]
        img_rot = img_original.rotate(-angulo_int, resample=Image.Resampling.BICUBIC, expand=False) if angulo_int != 0 else img_original
        img_tk = ImageTk.PhotoImage(img_rot)
        self._last_rot_key = (idx, angulo_int)
        self._last_rot_tk = img_tk
        return img_tk

    def atualizar_fisica(self):
        if not self.ativo or not self.root or not self.root.winfo_exists(): return

        self.frame_count += 1
        dist_mouse = math.hypot(self.mouse_x - self.last_mouse_x, self.mouse_y - self.last_mouse_y)
        if dist_mouse > 3: self.moving_cooldown = 15
        elif self.moving_cooldown > 0: self.moving_cooldown -= 1
        
        is_moving = self.moving_cooldown > 0
        self.last_mouse_x, self.last_mouse_y = self.mouse_x, self.mouse_y

        tamanho_corda = self.app.tamanho_corda.get()
        origem_corda_y = self.mouse_y + 8 

        if self.app.penduricalho_ativo.get():
            alvo_x = self.mouse_x
            alvo_y = origem_corda_y + tamanho_corda

            fx = (alvo_x - self.item_x) * self.app.rigidez.get()
            fy = (alvo_y - self.item_y) * self.app.rigidez.get()

            self.vx = (self.vx + fx) * self.app.amortecimento.get()
            self.vy = (self.vy + fy + self.app.gravidade_y.get()) * self.app.amortecimento.get()
            self.vx += self.app.gravidade_x.get()

            self.item_x += self.vx
            self.item_y += self.vy

            if self.app.corda_rigida.get():
                dx, dy = self.item_x - self.mouse_x, self.item_y - origem_corda_y
                dist = math.hypot(dx, dy)
                if dist > 0:
                    self.item_x = self.mouse_x + (dx/dist) * tamanho_corda
                    self.item_y = origem_corda_y + (dy/dist) * tamanho_corda

            dx_rot, dy_rot = self.mouse_x - self.item_x, origem_corda_y - self.item_y
            angulo_graus = 0.0
            if self.app.sensibilidade_rotacao.get() > 0:
                angulo_base = math.degrees(math.atan2(dy_rot, dx_rot)) - 90.0
                while angulo_base > 180: angulo_base -= 360
                while angulo_base < -180: angulo_base += 360
                angulo_graus = angulo_base * self.app.sensibilidade_rotacao.get()

        if self.frame_count % 4 == 0: self.anim_tick += 1
        frames_atuais = self.frames_moving if (is_moving and self.frames_moving) else self.frames_idle

        # Rastro
        if self.app.rastro_ativo.get() or self.app.part_ativo.get():
            self.rastro_pontos.append((self.mouse_x, origem_corda_y))
            max_tam = int(self.app.rastro_tam.get())
            if len(self.rastro_pontos) > max_tam:
                self.rastro_pontos.pop(0)

        # Partículas
        if self.app.part_ativo.get() and is_moving and self.frame_count % self.app.part_freq.get() == 0 and self.part_imgs:
            img = random.choice(self.part_imgs)
            disp = self.app.part_dispersao.get()
            
            vel_x_inicial = self.app.part_vel_x.get() + random.uniform(-disp, disp)
            vel_y_inicial = self.app.part_vel_y.get() + random.uniform(-disp, disp)
            
            self.particulas.append({
                'img': img, 'x': self.mouse_x, 'y': origem_corda_y, 
                'vx': vel_x_inicial, 'vy': vel_y_inicial, 'life': self.app.part_life.get()
            })

        # Desenhar no Canvas
        self.canvas.delete("all")
        
        if self.app.rastro_ativo.get() and len(self.rastro_pontos) > 1:
            coords = []
            for px, py in self.rastro_pontos:
                coords.extend([px, py])
            self.canvas.create_line(coords, fill=self.app.rastro_cor, 
                                    width=int(self.app.rastro_espessura.get()), 
                                    smooth=True, capstyle="round", joinstyle="round")

        novas_part = []
        for p in self.particulas:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vx'] += self.app.part_gx.get()
            p['vy'] += self.app.part_gy.get()
            
            p['life'] -= 1
            if p['life'] > 0:
                self.canvas.create_image(p['x'], p['y'], image=p['img'])
                novas_part.append(p)
        self.particulas = novas_part

        if self.app.penduricalho_ativo.get():
            if self.app.mostrar_corda.get():
                self.canvas.create_line(self.mouse_x, origem_corda_y, self.item_x, self.item_y, 
                                        fill=self.app.cor_corda, width=int(self.app.espessura_corda.get()))
            
            if frames_atuais:
                img_render = self.obter_frame_renderizado(frames_atuais, self.anim_tick, angulo_graus)
                if img_render: self.canvas.create_image(self.item_x, self.item_y, image=img_render)
            else:
                r = int(self.app.tamanho_item.get() / 2)
                self.canvas.create_oval(self.item_x-r, self.item_y-r, self.item_x+r, self.item_y+r, fill=self.app.cor_corda)

        self.root.after(16, self.atualizar_fisica)

    def parar(self):
        if not self.ativo: return
        self.ativo = False
        if self.listener: self.listener.stop()
        if self.root: self.root.destroy(); self.root = None


class AppInterface(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PenduriCursor")
        self.geometry("640x780")
        self.minsize(500, 600)
        self.resizable(True, True)

        self.COLOR_BG = "#18181a"
        self.COLOR_CARD = "#222226"
        self.COLOR_ACCENT = "#a0a0dc"
        self.COLOR_HOVER = "#8888c8"
        self.COLOR_TEXT_DIM = "#8e8e93"
        
        self.configure(fg_color=self.COLOR_BG)
        
        # Define o ícone no topo superior da janela
        self.iconbitmap("PenduriCursorIco.ico")
        
        self.overlay = OverlayPenduricalho(self)
        
        self.caminho_idle = ""
        self.caminho_moving = ""
        self.part_img = ""
        self.cor_corda = "#a0a0dc"
        self.rastro_cor = "#a0a0dc"

        self.penduricalho_ativo = ctk.BooleanVar(value=True)
        self.tamanho_item = ctk.DoubleVar(value=50)
        self.flip_x = ctk.BooleanVar(value=False)
        self.flip_y = ctk.BooleanVar(value=False)

        self.rastro_ativo = ctk.BooleanVar(value=False)
        self.rastro_tam = ctk.DoubleVar(value=20)
        self.rastro_espessura = ctk.DoubleVar(value=3)

        self.tamanho_corda = ctk.DoubleVar(value=35)
        self.espessura_corda = ctk.DoubleVar(value=2)
        self.mostrar_corda = ctk.BooleanVar(value=True)
        self.corda_rigida = ctk.BooleanVar(value=False)
        
        self.gravidade_x = ctk.DoubleVar(value=0.0)
        self.gravidade_y = ctk.DoubleVar(value=0.5)
        self.amortecimento = ctk.DoubleVar(value=0.82)
        self.rigidez = ctk.DoubleVar(value=0.08)
        self.sensibilidade_rotacao = ctk.DoubleVar(value=1.0)

        self.part_ativo = ctk.BooleanVar(value=False)
        self.part_var_tam = ctk.BooleanVar(value=True)
        self.part_tamanho = ctk.DoubleVar(value=24)
        self.part_freq = ctk.IntVar(value=3)
        self.part_life = ctk.IntVar(value=40)
        self.part_vel_x = ctk.DoubleVar(value=0.0)
        self.part_vel_y = ctk.DoubleVar(value=0.0)
        self.part_dispersao = ctk.DoubleVar(value=2.0)
        self.part_gx = ctk.DoubleVar(value=0.0)
        self.part_gy = ctk.DoubleVar(value=-0.2)

        self.protocol("WM_DELETE_WINDOW", self.ocultar_para_tray)

        self.criar_interface()
        self.carregar_preset_salvo()
        self.iniciar_tray_icon()

    def criar_interface(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=25, pady=(20, 10))

        ctk.CTkLabel(header_frame, text="PenduriCursor", font=("Segoe UI", 24, "bold"), text_color="#ffffff").pack(side="left")
        ctk.CTkLabel(header_frame, text="HUD Edition", font=("Segoe UI", 12), text_color=self.COLOR_ACCENT).pack(side="left", padx=10, pady=(8, 0))

        self.btn_toggle = ctk.CTkButton(
            self, text="Ligar App", font=("Segoe UI", 14, "bold"),
            fg_color=self.COLOR_ACCENT, hover_color=self.COLOR_HOVER, text_color="#18181a",
            height=40, command=self.toggle_overlay
        )
        self.btn_toggle.pack(pady=10, fill="x", padx=25)

        self.tabview = ctk.CTkTabview(
            self, fg_color=self.COLOR_CARD, segmented_button_fg_color=self.COLOR_BG,
            segmented_button_selected_color=self.COLOR_ACCENT,
            segmented_button_selected_hover_color=self.COLOR_HOVER,
            segmented_button_unselected_color=self.COLOR_CARD,
            segmented_button_unselected_hover_color="#2c2c30"
        )
        self.tabview.pack(pady=5, fill="both", expand=True, padx=25)

        tab_vis = self.tabview.add("Penduricalho")
        tab_fis = self.tabview.add("Física & Corda")
        tab_prt = self.tabview.add("Rastro Mágico")
        tab_pre = self.tabview.add("Presets")

        # Tab 1
        scroll_vis = ctk.CTkScrollableFrame(tab_vis, fg_color="transparent")
        scroll_vis.pack(fill="both", expand=True)
        ctk.CTkCheckBox(scroll_vis, text="Exibir Penduricalho", variable=self.penduricalho_ativo, font=("Segoe UI", 13, "bold"), fg_color=self.COLOR_ACCENT, hover_color=self.COLOR_HOVER).pack(pady=10)
        self.lbl_idle = self.criar_seletor_arquivo(scroll_vis, "Imagem Parado:", self.set_idle)
        self.lbl_move = self.criar_seletor_arquivo(scroll_vis, "Imagem Andando:", self.set_moving)
        self.criar_controle_num(scroll_vis, "Tamanho (px):", self.tamanho_item, 10, 300, self.atualizar_imagens_engine)
        
        f_flips = ctk.CTkFrame(scroll_vis, fg_color="transparent")
        f_flips.pack(pady=10)
        ctk.CTkCheckBox(f_flips, text="Espelhar Horizontal", variable=self.flip_x, fg_color=self.COLOR_ACCENT, command=self.atualizar_imagens_engine).pack(side="left", padx=10)
        ctk.CTkCheckBox(f_flips, text="De Ponta Cabeça", variable=self.flip_y, fg_color=self.COLOR_ACCENT, command=self.atualizar_imagens_engine).pack(side="left", padx=10)

        # Tab 2
        scroll_fis = ctk.CTkScrollableFrame(tab_fis, fg_color="transparent")
        scroll_fis.pack(fill="both", expand=True)
        ctk.CTkCheckBox(scroll_fis, text="Corda RÍGIDA (Não Estica)", variable=self.corda_rigida, fg_color=self.COLOR_ACCENT, font=("Segoe UI", 12, "bold")).pack(pady=(10,5))
        f_corda = ctk.CTkFrame(scroll_fis, fg_color=self.COLOR_BG)
        f_corda.pack(fill="x", padx=10, pady=5)
        ctk.CTkCheckBox(f_corda, text="Exibir Corda Visível", variable=self.mostrar_corda, fg_color=self.COLOR_ACCENT).pack(side="left", padx=10, pady=10)
        self.preview_cor = ctk.CTkFrame(f_corda, width=22, height=22, fg_color=self.cor_corda, corner_radius=11)
        self.preview_cor.pack(side="right", padx=15)
        ctk.CTkButton(f_corda, text="Cor", command=self.escolher_cor_corda, width=60, fg_color=self.COLOR_CARD, hover_color="#2c2c30").pack(side="right")
        self.criar_controle_num(scroll_fis, "Tamanho da Corda:", self.tamanho_corda, 0, 300)
        self.criar_controle_num(scroll_fis, "Espessura da Corda:", self.espessura_corda, 1, 10)
        ctk.CTkLabel(scroll_fis, text="-- COMPORTAMENTO FÍSICO --", font=("Segoe UI", 11, "bold"), text_color=self.COLOR_TEXT_DIM).pack(pady=(15,5))
        self.criar_controle_num(scroll_fis, "Gravidade Y (Cima/Baixo):", self.gravidade_y, -3.0, 3.0, passo=0.1)
        self.criar_controle_num(scroll_fis, "Gravidade X (Vento Lados):", self.gravidade_x, -3.0, 3.0, passo=0.1)
        self.criar_controle_num(scroll_fis, "Rotação Dinâmica:", self.sensibilidade_rotacao, 0.0, 3.0, passo=0.1)
        self.criar_controle_num(scroll_fis, "Mola/Resistência:", self.amortecimento, 0.1, 0.99, passo=0.01)
        self.criar_controle_num(scroll_fis, "Rigidez da Resposta:", self.rigidez, 0.01, 0.5, passo=0.01)

        # Tab 3
        scroll_rastro = ctk.CTkScrollableFrame(tab_prt, fg_color="transparent")
        scroll_rastro.pack(fill="both", expand=True)
        ctk.CTkLabel(scroll_rastro, text="-- LINHA DE RASTRO --", font=("Segoe UI", 12, "bold"), text_color=self.COLOR_TEXT_DIM).pack(pady=(5,0))
        f_linha = ctk.CTkFrame(scroll_rastro, fg_color=self.COLOR_BG)
        f_linha.pack(fill="x", padx=10, pady=5)
        ctk.CTkCheckBox(f_linha, text="Desenhar Linha", variable=self.rastro_ativo, fg_color=self.COLOR_ACCENT).pack(side="left", padx=10, pady=10)
        self.preview_rastro = ctk.CTkFrame(f_linha, width=22, height=22, fg_color=self.rastro_cor, corner_radius=11)
        self.preview_rastro.pack(side="right", padx=15)
        ctk.CTkButton(f_linha, text="Cor", command=self.escolher_cor_rastro, width=60, fg_color=self.COLOR_CARD, hover_color="#2c2c30").pack(side="right")
        self.criar_controle_num(scroll_rastro, "Comprimento da Linha:", self.rastro_tam, 2, 200)
        self.criar_controle_num(scroll_rastro, "Espessura da Linha:", self.rastro_espessura, 1, 20)
        ctk.CTkLabel(scroll_rastro, text="-- EMISSOR DE PARTÍCULAS --", font=("Segoe UI", 12, "bold"), text_color=self.COLOR_TEXT_DIM).pack(pady=(15,0))
        ctk.CTkCheckBox(scroll_rastro, text="Ligar Partículas", variable=self.part_ativo, fg_color=self.COLOR_ACCENT, font=("Segoe UI", 12, "bold")).pack(pady=5)
        self.lbl_part = self.criar_seletor_arquivo(scroll_rastro, "Imagem da Partícula:", self.set_part)
        ctk.CTkCheckBox(scroll_rastro, text="Variar Tamanho Aleatoriamente", variable=self.part_var_tam, fg_color=self.COLOR_ACCENT, command=self.atualizar_imagens_engine).pack(pady=5)
        self.criar_controle_num(scroll_rastro, "Tamanho Base:", self.part_tamanho, 5, 100, self.atualizar_imagens_engine)
        self.criar_controle_num(scroll_rastro, "Tempo de Vida:", self.part_life, 5, 200)
        self.criar_controle_num(scroll_rastro, "Frequência (Frames):", self.part_freq, 1, 30)
        ctk.CTkLabel(scroll_rastro, text="Física das Partículas:", font=("Segoe UI", 11, "italic"), text_color=self.COLOR_TEXT_DIM).pack(pady=(10,0))
        self.criar_controle_num(scroll_rastro, "Direção Inicial X:", self.part_vel_x, -5.0, 5.0, passo=0.5)
        self.criar_controle_num(scroll_rastro, "Direção Inicial Y:", self.part_vel_y, -5.0, 5.0, passo=0.5)
        self.criar_controle_num(scroll_rastro, "Espalhamento:", self.part_dispersao, 0.0, 10.0, passo=0.5)
        self.criar_controle_num(scroll_rastro, "Gravidade Y:", self.part_gy, -2.0, 2.0, passo=0.1)
        self.criar_controle_num(scroll_rastro, "Vento X:", self.part_gx, -2.0, 2.0, passo=0.1)

        # Tab 4
        f_presets = ctk.CTkFrame(tab_pre, fg_color="transparent")
        f_presets.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(f_presets, text="Gerenciador de Presets", font=("Segoe UI", 14, "bold")).pack(pady=(5, 10))
        self.entry_preset_name = ctk.CTkEntry(f_presets, placeholder_text="Nome do Preset...", fg_color=self.COLOR_BG)
        self.entry_preset_name.pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(f_presets, text="Salvar Novo Preset", fg_color=self.COLOR_ACCENT, hover_color=self.COLOR_HOVER, text_color="#18181a", command=self.salvar_novo_preset).pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f_presets, text="Presets Salvos:", font=("Segoe UI", 11, "bold"), text_color=self.COLOR_TEXT_DIM).pack(pady=(10, 5))
        self.scroll_presets = ctk.CTkScrollableFrame(f_presets, fg_color=self.COLOR_BG)
        self.scroll_presets.pack(fill="both", expand=True, padx=20, pady=5)
        self.lbl_status = ctk.CTkLabel(f_presets, text="", font=("Segoe UI", 11))
        self.lbl_status.pack(pady=5)
        self.atualizar_lista_presets()

    def criar_seletor_arquivo(self, parent, titulo, callback):
        f = ctk.CTkFrame(parent, fg_color=self.COLOR_BG)
        f.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f, text=titulo, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=(5,0))
        btn = ctk.CTkButton(f, text="Selecionar", width=80, fg_color=self.COLOR_CARD, hover_color="#2c2c30", command=callback)
        btn.pack(side="right", padx=10, pady=5)
        lbl = ctk.CTkLabel(f, text="Nenhum...", text_color=self.COLOR_TEXT_DIM, font=("Segoe UI", 10))
        lbl.pack(side="left", padx=10, pady=5)
        return lbl

    def set_idle(self):
        c = filedialog.askopenfilename(filetypes=[("Imagens", "*.png *.gif")])
        if c: self.caminho_idle = c; self.lbl_idle.configure(text=os.path.basename(c)); self.atualizar_imagens_engine()

    def set_moving(self):
        c = filedialog.askopenfilename(filetypes=[("Imagens", "*.png *.gif")])
        if c: self.caminho_moving = c; self.lbl_move.configure(text=os.path.basename(c)); self.atualizar_imagens_engine()

    def set_part(self):
        c = filedialog.askopenfilename(filetypes=[("Imagens", "*.png *.gif")])
        if c: self.part_img = c; self.lbl_part.configure(text=os.path.basename(c)); self.atualizar_imagens_engine()

    def atualizar_imagens_engine(self, *args):
        if self.overlay.ativo: self.overlay.carregar_imagens()

    def criar_controle_num(self, parent, titulo, variavel, de, ate, callback=None, passo=1.0):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(frame, text=titulo, font=("Segoe UI", 11)).pack(side="left")
        e = ctk.CTkEntry(frame, width=50, height=22, fg_color=self.COLOR_BG)
        e.pack(side="right")
        
        def sync_e(*_): 
            try: variavel.set(float(e.get())); (callback() if callback else None)
            except ValueError: pass
        def sync_v(*_): e.delete(0, tk.END); e.insert(0, f"{variavel.get():.2f}".rstrip('0').rstrip('.'))
        
        e.bind("<Return>", sync_e); e.bind("<FocusOut>", sync_e)
        sync_v()
        
        ctk.CTkSlider(
            frame, from_=de, to=ate, variable=variavel, width=120,
            button_color=self.COLOR_ACCENT, button_hover_color=self.COLOR_HOVER,
            command=lambda v: (sync_v(), callback() if callback else None)
        ).pack(side="right", padx=10)

    def escolher_cor_corda(self):
        cor = colorchooser.askcolor(initialcolor=self.cor_corda)
        if cor[1]: self.cor_corda = cor[1]; self.preview_cor.configure(fg_color=self.cor_corda)
        
    def escolher_cor_rastro(self):
        cor = colorchooser.askcolor(initialcolor=self.rastro_cor)
        if cor[1]: self.rastro_cor = cor[1]; self.preview_rastro.configure(fg_color=self.rastro_cor)

    def toggle_overlay(self):
        if self.overlay.ativo:
            self.overlay.parar()
            self.btn_toggle.configure(text="Ligar App", fg_color=self.COLOR_ACCENT, hover_color=self.COLOR_HOVER)
        else:
            self.overlay.iniciar()
            self.btn_toggle.configure(text="Desligar App", fg_color="#e53935", hover_color="#c62828")

    def obter_dados_atuais(self):
        return {
            "pend_ativo": self.penduricalho_ativo.get(),
            "idle": self.caminho_idle, "move": self.caminho_moving, "part_img": self.part_img,
            "cor": self.cor_corda, "tam": self.tamanho_item.get(), "corda": self.tamanho_corda.get(),
            "esp": self.espessura_corda.get(), "mostrar": self.mostrar_corda.get(),
            "rigida": self.corda_rigida.get(), "fx": self.flip_x.get(), "fy": self.flip_y.get(),
            "gx": self.gravidade_x.get(), "gy": self.gravidade_y.get(), "rot": self.sensibilidade_rotacao.get(),
            "amort": self.amortecimento.get(), "rig": self.rigidez.get(),
            "r_ativo": self.rastro_ativo.get(), "r_tam": self.rastro_tam.get(),
            "r_esp": self.rastro_espessura.get(), "r_cor": self.rastro_cor,
            "p_ativo": self.part_ativo.get(), "p_var": self.part_var_tam.get(),
            "p_tam": self.part_tamanho.get(), "p_disp": self.part_dispersao.get(),
            "p_freq": self.part_freq.get(), "p_life": self.part_life.get(), 
            "p_vx": self.part_vel_x.get(), "p_vy": self.part_vel_y.get(),
            "p_gx": self.part_gx.get(), "p_gy": self.part_gy.get()
        }

    def aplicar_dados(self, d):
        self.penduricalho_ativo.set(d.get("pend_ativo", True))
        self.caminho_idle = d.get("idle", "")
        self.lbl_idle.configure(text=os.path.basename(self.caminho_idle) if self.caminho_idle else "Nenhum...")
        
        self.caminho_moving = d.get("move", "")
        self.lbl_move.configure(text=os.path.basename(self.caminho_moving) if self.caminho_moving else "Nenhum...")
        
        self.part_img = d.get("part_img", "")
        self.lbl_part.configure(text=os.path.basename(self.part_img) if self.part_img else "Nenhum...")
        
        self.cor_corda = d.get("cor", "#a0a0dc")
        self.preview_cor.configure(fg_color=self.cor_corda)
        
        self.tamanho_item.set(d.get("tam", 50))
        self.tamanho_corda.set(d.get("corda", 35))
        self.espessura_corda.set(d.get("esp", 2))
        self.mostrar_corda.set(d.get("mostrar", True))
        self.corda_rigida.set(d.get("rigida", False))
        self.flip_x.set(d.get("fx", False))
        self.flip_y.set(d.get("fy", False))
        self.gravidade_x.set(d.get("gx", 0.0))
        self.gravidade_y.set(d.get("gy", 0.5))
        self.sensibilidade_rotacao.set(d.get("rot", 1.0))
        self.amortecimento.set(d.get("amort", 0.82))
        self.rigidez.set(d.get("rig", 0.08))

        self.rastro_ativo.set(d.get("r_ativo", False))
        self.rastro_tam.set(d.get("r_tam", 20))
        self.rastro_espessura.set(d.get("r_esp", 3))
        self.rastro_cor = d.get("r_cor", "#a0a0dc")
        self.preview_rastro.configure(fg_color=self.rastro_cor)

        self.part_ativo.set(d.get("p_ativo", False))
        self.part_var_tam.set(d.get("p_var", True))
        self.part_tamanho.set(d.get("p_tam", 24))
        self.part_dispersao.set(d.get("p_disp", 2.0))
        self.part_freq.set(d.get("p_freq", 3))
        self.part_life.set(d.get("p_life", 40))
        self.part_vel_x.set(d.get("p_vx", 0.0))
        self.part_vel_y.set(d.get("p_vy", 0.0))
        self.part_gx.set(d.get("p_gx", 0.0))
        self.part_gy.set(d.get("p_gy", -0.2))
        self.atualizar_imagens_engine()

    def salvar_preset_padrao(self):
        d = self.obter_dados_atuais()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=4)

    def carregar_preset_salvo(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                self.aplicar_dados(d)
                self.lbl_status.configure(text="Configurações salvas carregadas!", text_color=self.COLOR_ACCENT)
            except Exception: pass

    def salvar_novo_preset(self):
        nome = self.entry_preset_name.get().strip()
        if not nome:
            messagebox.showwarning("PenduriCursor", "Digite um nome para o preset.")
            return

        folder = os.path.join(PRESETS_DIR, nome)
        os.makedirs(folder, exist_ok=True)

        d = self.obter_dados_atuais()

        for chave, caminho in [("idle", self.caminho_idle), ("move", self.caminho_moving), ("part_img", self.part_img)]:
            if caminho and os.path.exists(caminho):
                nome_arq = os.path.basename(caminho)
                destino = os.path.join(folder, nome_arq)
                try:
                    shutil.copy2(caminho, destino)
                    d[chave] = destino
                except Exception: pass

        with open(os.path.join(folder, "preset.json"), "w", encoding="utf-8") as f:
            json.dump(d, f, indent=4)

        self.entry_preset_name.delete(0, tk.END)
        self.lbl_status.configure(text=f"Preset '{nome}' salvo!", text_color=self.COLOR_ACCENT)
        self.atualizar_lista_presets()

    def carregar_preset_pasta(self, pasta_nome):
        folder = os.path.join(PRESETS_DIR, pasta_nome)
        json_path = os.path.join(folder, "preset.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.aplicar_dados(d)
            self.salvar_preset_padrao()
            self.lbl_status.configure(text=f"Preset '{pasta_nome}' aplicado!", text_color=self.COLOR_ACCENT)

    def atualizar_lista_presets(self):
        for widget in self.scroll_presets.winfo_children():
            widget.destroy()

        if not os.path.exists(PRESETS_DIR): return

        presets = [d for d in os.listdir(PRESETS_DIR) if os.path.isdir(os.path.join(PRESETS_DIR, d))]
        if not presets:
            ctk.CTkLabel(self.scroll_presets, text="Nenhum preset salvo.", text_color=self.COLOR_TEXT_DIM).pack(pady=10)
            return

        for p in presets:
            f = ctk.CTkFrame(self.scroll_presets, fg_color=self.COLOR_CARD)
            f.pack(fill="x", pady=3, padx=5)
            ctk.CTkLabel(f, text=p, font=("Segoe UI", 11, "bold")).pack(side="left", padx=10)
            ctk.CTkButton(
                f, text="Carregar", width=60, fg_color=self.COLOR_ACCENT, hover_color=self.COLOR_HOVER,
                text_color="#18181a", command=lambda nome=p: self.carregar_preset_pasta(nome)
            ).pack(side="right", padx=5, pady=5)

    def criar_imagem_tray(self):
        try:
            return Image.open("PenduriCursorIco.ico")
        except Exception:
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse((8, 8, 56, 56), fill="#a0a0dc")
            return img

    def iniciar_tray_icon(self):
        menu = pystray.Menu(
            pystray.MenuItem("Abrir", self.mostrar_janela, default=True),
            pystray.MenuItem("Sair", self.encerrar_aplicacao)
        )
        self.tray_icon = pystray.Icon("PenduriCursor", self.criar_imagem_tray(), "PenduriCursor", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def ocultar_para_tray(self):
        self.salvar_preset_padrao()
        self.withdraw()

    def mostrar_janela(self, icon=None, item=None):
        self.deiconify()
        self.focus_force()

    def encerrar_aplicacao(self, icon=None, item=None):
        self.salvar_preset_padrao()
        self.overlay.parar()
        if self.tray_icon:
            self.tray_icon.stop()
        self.after(0, self.destroy)


if __name__ == "__main__":
    app = AppInterface()
    app.mainloop()