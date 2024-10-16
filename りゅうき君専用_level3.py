# cv2のインポート前にカメラに関する設定を行う
import os
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"
import socket
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2, numpy, time, sys, struct, pickle
import threading, queue

q = queue.Queue()       #受信する画像データをスレッド間で共有するためのキュー

msg_q = queue.Queue()   #障害物情報を保持するキュー

state_q = queue.Queue() #ロボットの状態を保持するキュー

# グローバル変数としてソケットを定義
client_socket = None
client_socket_s = None

state_flag = False   #衝突防止動作によってロボットが停止したかどうかを判断するブール値(False：停止, True：動作中)

mode_flag = True # ユーザ操縦モードか介助者操縦モードかを判断するための変数（True：ユーザ操縦モード、False：介助者操縦モード）

class MyApp(tk.Tk):

    '''ボタンやキャンバスの設定、表示'''
    def __init__(self, *args, **kwargs):  
        tk.Tk.__init__(self, *args, **kwargs)

        #ウィンドウタイトル
        self.title("GUI_for_gaze input")

        #ウィンドウサイズ
        self.geometry('1275x765')

        #配置がずれないようにウィンドウのグリッドを1×1に設定
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        global mode_flag 

        self.flag = 'M_F'   #フレームごとで映像を表示するためのフラグ

        self.arg = False   #画面遷移したかどうか

        self.str_state = False   #衝突防止動作の実行前にロボットが動いていたかを判断する

        self.str = [False] * 10 # 遷移後の画面でもシンボルロックするために前回の障害物情報を保持するための配列

        # 前方、後方カメラをオープンする
        self.capture_F = cv2.VideoCapture(1)
        self.capture_B = cv2.VideoCapture(2)  

        # 速度・検知範囲用のconfigファイル用変数
        file_path = 'vel_and_detect_range_config.txt' 
        host = '192.168.1.102' 
        port = 65432

        self.send_config(file_path, host, port)

        '''シンボル画像用意'''
        #コンフィグレーションファイルからシンボル拡大率（W、H）、透明度（ALPHA）を読込
        self.config = self.read_config('config.txt')
        W = float(self.config['W'])
        H = float(self.config['H'])
        self.alpha = int(self.config.get('ALPHA', 128))

        '''シンボル画像を設定'''
        # 走行開始シンボル
        self.img_start = Image.open('start.png')
        self.img_start = self.img_start.resize((int(200 * W), int(200 * H)))
        self.img_start = self.img_start.convert("RGBA")
        self.img_start = self.apply_transparency(self.img_start, self.alpha)
        self.img_start_tk = ImageTk.PhotoImage(self.img_start)
        # 後方の走行開始シンボル
        self.img_start_back = Image.open('start_back.png')
        self.img_start_back = self.img_start_back.resize((int(200 * W), int(200 * H)))
        self.img_start_back = self.img_start_back.convert("RGBA")
        self.img_start_back = self.apply_transparency(self.img_start_back, self.alpha)
        self.img_strat_back_tk = ImageTk.PhotoImage(self.img_start_back)
        # 終了シンボル
        self.img_finish = Image.open('finish_letter.png')
        self.img_finish = self.img_finish.resize((150, 100))
        self.img_finish = self.img_finish.convert("RGBA")
        self.img_finish = self.apply_transparency(self.img_finish, self.alpha)
        self.img_finish_tk = ImageTk.PhotoImage(self.img_finish)
        # 前方向への画面遷移シンボル
        self.img_change_forward = Image.open('change_forward_joy.png')
        self.img_change_forward = self.img_change_forward.resize((200, 200))
        self.img_change_forward = self.img_change_forward.convert("RGBA")
        self.img_change_forward = self.apply_transparency(self.img_change_forward, self.alpha)
        self.img_change_forward_tk = ImageTk.PhotoImage(self.img_change_forward)
        # 後ろ方向への画面遷移シンボル
        self.img_change_back = Image.open('change_back_joy.png')
        self.img_change_back = self.img_change_back.resize((200, 200))
        self.img_change_back = self.img_change_back.convert("RGBA")
        self.img_change_back = self.apply_transparency(self.img_change_back, self.alpha)
        self.img_change_back_tk = ImageTk.PhotoImage(self.img_change_back)
        # メニューへの画面遷移シンボル
        self.img_menu = Image.open('menu.png')
        self.img_menu = self.img_menu.resize((200, 100))
        self.img_menu = self.img_menu.convert("RGBA")
        self.img_menu = self.apply_transparency(self.img_menu, self.alpha)
        self.img_menu_tk = ImageTk.PhotoImage(self.img_menu)
       # 介助者操縦モードのシンボル
        self.img_helper = Image.open('helper.png')
        self.img_helper = self.img_helper.resize((200, 100))
        self.img_helper = self.img_helper.convert("RGBA")
        self.img_helper = self.apply_transparency(self.img_helper, self.alpha)
        self.img_helper_tk = ImageTk.PhotoImage(self.img_helper)
        # ユーザ操縦モードのシンボル
        self.img_user = Image.open("user.png")
        self.img_user = self.img_user.resize((200, 100))
        self.img_user = self.img_user.convert("RGBA")
        self.img_user = self.apply_transparency(self.img_user, self.alpha)
        self.img_user_tk = ImageTk.PhotoImage(self.img_user)
        # 前進シンボル
        self.img_forward = Image.open('forward_3d.png')
        self.img_forward = self.img_forward.resize((int(120 * W), int(120 * H)))
        self.img_forward = self.img_forward.convert("RGBA")
        self.img_forward = self.apply_transparency(self.img_forward, self.alpha)
        self.img_forward_tk = ImageTk.PhotoImage(self.img_forward)
        # 後退シンボル
        self.img_back = Image.open('back_3d.png')
        self.img_back = self.img_back.resize((int(120 * W), int(120 * H)))
        self.img_back = self.img_back.convert("RGBA")
        self.img_back = self.apply_transparency(self.img_back, self.alpha)
        self.img_back_tk = ImageTk.PhotoImage(self.img_back)
        # cw旋回シンボル
        self.img_cw = Image.open('cw_3d.png')
        self.img_cw = self.img_cw.resize((int(120 * W), int(120 * H)))
        self.img_cw = self.img_cw.convert("RGBA")
        self.img_cw = self.apply_transparency(self.img_cw, self.alpha)
        self.img_cw_tk = ImageTk.PhotoImage(self.img_cw)
        # ccw旋回シンボル
        self.img_ccw = Image.open('ccw_3d.png')
        self.img_ccw = self.img_ccw.resize((int(120 * W), int(120 * H)))
        self.img_ccw = self.img_ccw.convert("RGBA")
        self.img_ccw = self.apply_transparency(self.img_ccw, self.alpha)
        self.img_ccw_tk = ImageTk.PhotoImage(self.img_ccw)
        #停止シンボル
        self.img_stop = Image.open('stop_3d.png')
        self.img_stop = self.img_stop.resize((int(120 * W), int(120 * H)))
        self.img_stop = self.img_stop.convert("RGBA")
        self.img_stop = self.apply_transparency(self.img_stop, self.alpha)
        self.img_stop_tk = ImageTk.PhotoImage(self.img_stop)
        #前進ロックシンボル
        self.img_lock_forward = Image.open('forward_3d_lock.png')
        self.img_lock_forward = self.img_lock_forward.resize((int(120 * W), int(120 * H)))
        self.img_lock_forward = self.img_lock_forward.convert("RGBA")
        self.img_lock_forward = self.apply_transparency(self.img_lock_forward, self.alpha)
        self.img_lock_forward_tk = ImageTk.PhotoImage(self.img_lock_forward)
        #後退ロックシンボル
        self.img_lock_back = Image.open('back_3d_lock.png')
        self.img_lock_back = self.img_lock_back.resize((int(120 * W), int(120 * H)))
        self.img_lock_back = self.img_lock_back.convert("RGBA")
        self.img_lock_back = self.apply_transparency(self.img_lock_back, self.alpha)
        self.img_lock_back_tk = ImageTk.PhotoImage(self.img_lock_back) 
        #cw旋回ロックシンボル
        self.img_lock_cw = Image.open('cw_3d_lock.png')
        self.img_lock_cw = self.img_lock_cw.resize((int(120 * W), int(120 * H)))
        self.img_lock_cw = self.img_lock_cw.convert("RGBA")
        self.img_lock_cw = self.apply_transparency(self.img_lock_cw, self.alpha)
        self.img_lock_cw_tk = ImageTk.PhotoImage(self.img_lock_cw)
        #ccw旋回ロックシンボル
        self.img_lock_ccw = Image.open('ccw_3d_lock.png')
        self.img_lock_ccw = self.img_lock_ccw.resize((int(120 * W), int(120 * H)))
        self.img_lock_ccw = self.img_lock_ccw.convert("RGBA")
        self.img_lock_ccw = self.apply_transparency(self.img_lock_ccw, self.alpha)
        self.img_lock_ccw_tk = ImageTk.PhotoImage(self.img_lock_ccw)

        '''シンボルサイズに合わせた配置座標を設定'''
        # 前進と後退シンボルの座標
        self.X_straight = 637
        self.Y_straight = 200

        # cw旋回シンボルの座標
        self.X_cw = 140 * (W - 1) + 757
        self.Y_cw = 333

        # ccw旋回シンボルの座標
        self.X_ccw = -140 * (W - 1) + 517
        self.Y_ccw = 333

        # 停止シンボルの座標
        self.X_stop = 637
        self.Y_stop = 75 * (W - 1) + 453

        '''各画面のフレーム作成'''
        #-----------------------------forward_menu_frame------------------------------
        #前方メニュー画面フレーム作成
        self.menu_frame = ttk.Frame()
        self.menu_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_menu = tk.Canvas(self.menu_frame,width=1275,height=765)
        self.cvs_menu.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )
        
        # 走行開始シンボル
        self.id_menu = self.cvs_menu.create_image(
            637,
            350,
            image = self.img_start_tk,
            anchor = tk.CENTER,
        )
        self.cvs_menu.tag_bind(
            self.id_menu,
            '<Button-1>',
            lambda e: [self.start_running()]
            )

        # 終了シンボル
        self.id_finish = self.cvs_menu.create_image(
            1195,
            720,
            image = self.img_finish_tk,
            anchor = tk.CENTER,
        )
        self.cvs_menu.tag_bind(
            self.id_finish,
            '<Button-1>',
            lambda e: [self.Finish()]
            )

        # 介助者操縦モードシンボル
        self.id_F_helper = self.cvs_menu.create_image(
            300,
            720,
            image = self.img_helper_tk,
            anchor = tk.CENTER,
        )
        self.cvs_menu.tag_bind(
            self.id_F_helper,
            '<Button-1>',
            lambda e: [self.changePage(self.menu_helper_F_frame), self.change_frame_flag("H_F"), self.helper()]
            )

        #-----------------------------back_menu_frame------------------------------
        #後方メニュー画面フレーム作成
        self.menu_back_frame = ttk.Frame()
        self.menu_back_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_menu_back = tk.Canvas(self.menu_back_frame,width=1275,height=765)
        self.cvs_menu_back.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )
        
        # 走行開始シンボル
        self.id_menu_back = self.cvs_menu_back.create_image(
            637,
            350,
            image = self.img_strat_back_tk,
            anchor = tk.CENTER,
        )
        self.cvs_menu_back.tag_bind(
            self.id_menu_back,
            '<Button-1>',
            lambda e: [self.start_running()]
            )

        # 終了シンボル
        self.id_finish_back = self.cvs_menu_back.create_image(
            1195,
            720,
            image = self.img_finish_tk,
            anchor = tk.CENTER,
        )
        self.cvs_menu_back.tag_bind(
            self.id_finish_back,
            '<Button-1>',
            lambda e: [self.Finish()]
            )

        # 介助者操縦モードシンボル
        self.id_B_helper = self.cvs_menu_back.create_image(
            300,
            720,
            image = self.img_helper_tk,
            anchor = tk.CENTER,
        )
        self.cvs_menu_back.tag_bind(
            self.id_B_helper,
            '<Button-1>',
            lambda e: [self.changePage(self.menu_helper_B_frame), self.change_frame_flag("H_B"), self.helper()]
            )

        #-----------------------------menu_helper_F_frame------------------------------
        #介助者前方画面フレーム作成
        self.menu_helper_F_frame = ttk.Frame()
        self.menu_helper_F_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_menu_helper_F = tk.Canvas(self.menu_helper_F_frame,width=1275,height=765)
        self.cvs_menu_helper_F.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )

        # 走行開始シンボル
        self.id_start_helper_F = self.cvs_menu_helper_F.create_image(
            637,
            350,
            image = self.img_start_tk,
            anchor = tk.CENTER,
        )
        self.cvs_menu_helper_F.tag_bind(
            self.id_start_helper_F,
            '<Button-1>',
            lambda e: [self.start_running()]
            )

        # 終了シンボル
        self.id_finish_helper_F = self.cvs_menu_helper_F.create_image(
            1195,
            720,
            image = self.img_finish_tk,
            anchor = tk.CENTER,
        )
        self.cvs_menu_helper_F.tag_bind(
            self.id_finish_helper_F,
            '<Button-1>',
            lambda e: [self.Finish()]
            )

        # ユーザ操縦モードシンボル
        self.id_F_user = self.cvs_menu_helper_F.create_image(
            100,
            720,
            image = self.img_user_tk,
            anchor = tk.CENTER,
        )
        self.cvs_menu_helper_F.tag_bind(
            self.id_F_user,
            '<Button-1>',
            lambda e: [self.changePage(self.menu_frame), self.change_frame_flag("M_F"), self.user()]
            )        

        #-----------------------------menu_helper_B_frame------------------------------
        #前方画面フレーム作成
        self.menu_helper_B_frame = ttk.Frame()
        self.menu_helper_B_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_menu_helper_B = tk.Canvas(self.menu_helper_B_frame,width=1275,height=765)
        self.cvs_menu_helper_B.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )

        # 走行開始シンボル
        self.id_start_helper_B = self.cvs_menu_helper_B.create_image(
            637,
            350,
            image = self.img_strat_back_tk,
            anchor = tk.CENTER,
        )
        self.cvs_menu_helper_B.tag_bind(
            self.id_start_helper_B,
            '<Button-1>',
            lambda e: [self.start_running()]
            )

        # 終了シンボル
        self.id_finish_helper_B = self.cvs_menu_helper_B.create_image(
            1195,
            720,
            image = self.img_finish_tk,
            anchor = tk.CENTER,
        )
        self.cvs_menu_helper_B.tag_bind(
            self.id_finish_helper_B,
            '<Button-1>',
            lambda e: [self.Finish()]
            )

        # ユーザ操縦モードシンボル
        self.id_B_user = self.cvs_menu_helper_B.create_image(
            100,
            720,
            image = self.img_user_tk,
            anchor = tk.CENTER,
        )
        self.cvs_menu_helper_B.tag_bind(
            self.id_B_user,
            '<Button-1>',
            lambda e: [self.changePage(self.menu_back_frame), self.change_frame_flag("M_B"), self.user()]
            )
        
        #-----------------------stop__forward_frame-------------------------------------
        #前方走行中の停止時フレームを作成
        self.stop_forward_frame = ttk.Frame()
        self.stop_forward_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_stop_forward = tk.Canvas(self.stop_forward_frame,width=1275,height=765)
        self.cvs_stop_forward.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )

        ###シンボル設置###
        
        '''ロックシンボル'''
        #停止画面の前進ロックシンボル
        self.id_lock_S_F_forward = self.cvs_stop_forward.create_image(
            self.X_straight,
            self.Y_straight,
            image = self.img_lock_forward_tk,
            anchor = tk.CENTER,
            tag = "lock_S_F_forward"
        )

        #停止画面のcw旋回ロックシンボル
        self.id_lock_S_F_cw = self.cvs_stop_forward.create_image(
            self.X_cw,
            self.Y_cw,
            image = self.img_lock_cw_tk,
            anchor = tk.CENTER,
            tag = "lock_S_F_cw"
        )
        
        #停止画面のccw旋回ロックシンボル
        self.id_lock_S_F_ccw = self.cvs_stop_forward.create_image(
            self.X_ccw,
            self.Y_ccw,
            image = self.img_lock_ccw_tk,
            anchor = tk.CENTER,
            tag = "lock_S_F_ccw"
        )
        ''''''
        '''ロボット操縦シンボル'''
        # 前進シンボル
        self.id_S_F_forward = self.cvs_stop_forward.create_image(
            self.X_straight,
            self.Y_straight,
            image = self.img_forward_tk,
            anchor = tk.CENTER,
            tag = "S_F_forward"
        )
        self.cvs_stop_forward.tag_bind(
            self.id_S_F_forward,
            '<Button-1>',
            lambda e: [self.changePage(self.forward_frame), self.change_frame_flag("F"), self.forward(), self.start_blinking(self.id_forward)]
            #lambda e: [self.change_frame_flag("F"), self.forward(), self.start_blinking(self.id_forward), self.changePage(self.forward_frame)]
            )

        # cw旋回シンボル
        self.id_S_F_cw = self.cvs_stop_forward.create_image(
            self.X_cw,
            self.Y_cw,
            image = self.img_cw_tk,
            anchor = tk.CENTER,
            tag = "S_F_cw"
        )
        self.cvs_stop_forward.tag_bind(
            self.id_S_F_cw,
            '<Button-1>',
            lambda e: [self.changePage(self.forward_frame), self.change_frame_flag("F"), self.cw(), self.start_blinking(self.id_F_cw)]
            )

        # ccw旋回シンボル
        self.id_S_F_ccw = self.cvs_stop_forward.create_image(
            self.X_ccw,
            self.Y_ccw,
            image = self.img_ccw_tk,
            anchor = tk.CENTER,
            tag = "S_F_ccw"
        )
        self.cvs_stop_forward.tag_bind(
            self.id_S_F_ccw,
            '<Button-1>',
            lambda e: [self.changePage(self.forward_frame), self.change_frame_flag("F"), self.ccw(), self.start_blinking(self.id_F_ccw)]
            )

        '''ロボット操縦以外のシンボル'''
        # 後方画面に遷移するシンボル
        self.id_change_back = self.cvs_stop_forward.create_image(
            820,
            652,
            image = self.img_change_back_tk,
            anchor = tk.CENTER,
        )
        self.cvs_stop_forward.tag_bind(
            self.id_change_back,
            '<Button-1>',
            lambda e: [self.changePage(self.stop_back_frame), self.change_frame_flag("S_B"), self.stop_blink()]
            )
        
        # メニュー画面に遷移するシンボル
        self.id_change_menu = self.cvs_stop_forward.create_image(
            110,
            682,
            image = self.img_menu_tk,
            anchor = tk.CENTER,
        )
        self.cvs_stop_forward.tag_bind(
            self.id_change_menu,
            '<Button-1>',
            lambda e: [self.menu()]
            )        
        ''''''            

        #-----------------------stop_back_frame-------------------------------------
        #後方の停止時フレームを作成
        self.stop_back_frame = ttk.Frame()
        self.stop_back_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_stop_back = tk.Canvas(self.stop_back_frame,width=1275,height=765)
        self.cvs_stop_back.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )

        '''ロックシンボル'''
        #停止画面の後退ロックシンボル
        self.id_lock_S_B_back = self.cvs_stop_back.create_image(
            self.X_straight,
            self.Y_straight,
            image = self.img_lock_back_tk,
            anchor = tk.CENTER,
            tag = "lock_S_B_back"
        )

        #停止画面のcw旋回ロックシンボル
        self.id_lock_S_B_cw = self.cvs_stop_back.create_image(
            self.X_cw,
            self.Y_cw,
            image = self.img_lock_cw_tk,
            anchor = tk.CENTER,
            tag = "lock_S_B_cw"
        )

        #停止画面のccw旋回ロックシンボル
        self.id_lock_S_B_ccw = self.cvs_stop_back.create_image(
            self.X_ccw,
            self.Y_ccw,
            image = self.img_lock_ccw_tk,
            anchor = tk.CENTER,
            tag = "lock_S_B_cw"
        )

        '''ロボット操縦シンボル'''
        # 後退シンボル
        self.id_S_B_back = self.cvs_stop_back.create_image(
            self.X_straight,
            self.Y_straight,
            image = self.img_back_tk,
            anchor = tk.CENTER,
            tag = "S_B_back"
        )
        self.cvs_stop_back.tag_bind(
            self.id_S_B_back,
            '<Button-1>',
            lambda e: [self.changePage(self.back_frame), self.change_frame_flag("B"), self.back(), self.start_blinking(self.id_back)]
            )

        # cw旋回シンボル
        self.id_S_B_cw = self.cvs_stop_back.create_image(
            self.X_cw,
            self.Y_cw,
            image = self.img_cw_tk,
            anchor = tk.CENTER,
            tag = "S_B_cw"
        )
        self.cvs_stop_back.tag_bind(
            self.id_S_B_cw,
            '<Button-1>',
            lambda e: [self.changePage(self.back_frame), self.change_frame_flag("B"), self.cw(), self.start_blinking(self.id_B_cw)]
            )

        # ccw旋回シンボル
        self.id_S_B_ccw = self.cvs_stop_back.create_image(
            self.X_ccw,
            self.Y_ccw,
            image = self.img_ccw_tk,
            anchor = tk.CENTER,
            tag = "S_B_ccw"
        )
        self.cvs_stop_back.tag_bind(
            self.id_S_B_ccw,
            '<Button-1>',
            lambda e: [self.changePage(self.back_frame), self.change_frame_flag("B"), self.cw(), self.start_blinking(self.id_B_cw)]
            )
        
        '''ロボット操作以外のシンボル'''
        # 前方画面に遷移するシンボル
        self.id_change_forward = self.cvs_stop_back.create_image(
            620,
            652,
            image = self.img_change_forward_tk,
            anchor = tk.CENTER,
        )
        self.cvs_stop_back.tag_bind(
            self.id_change_forward,
            '<Button-1>',
            lambda e: [self.changePage(self.stop_forward_frame), self.change_frame_flag("S_F"), self.stop_blink()]
            )
        
        # メニュー画面に遷移するシンボル
        self.id_change_menu_back = self.cvs_stop_back.create_image(
            110,
            682,
            image = self.img_menu_tk,
            anchor = tk.CENTER,
        )
        self.cvs_stop_back.tag_bind(
            self.id_change_menu_back,
            '<Button-1>',
            lambda e: [self.menu()]
            )        
        ''''''

        #-----------------------------forward_frame------------------------------

        #前方走行時画面フレーム作成
        self.forward_frame = ttk.Frame()
        self.forward_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_forward = tk.Canvas(self.forward_frame,width=1275,height=765)
        self.cvs_forward.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )

        ###シンボル設置###
        '''ロックシンボル'''
        # 前進ロック
        self.id_lock_forward = self.cvs_forward.create_image(
            self.X_straight,
            self.Y_straight,
            image = self.img_lock_forward_tk,
            anchor = tk.CENTER,
            tag = "lock_forward"
        )

        # cwロック
        self.id_lock_F_cw = self.cvs_forward.create_image(
            self.X_cw,
            self.Y_cw,
            image = self.img_lock_cw_tk,
            anchor = tk.CENTER,
            tag = "lock_F_cw_"
        )

        # ccwロック
        self.id_lock_F_ccw = self.cvs_forward.create_image(
            self.X_ccw,
            self.Y_ccw,
            image = self.img_lock_ccw_tk,
            anchor = tk.CENTER,
            tag = "lock_F_ccw"
        )

        '''ロボット操縦シンボル'''
        # 前進シンボル
        self.id_forward = self.cvs_forward.create_image(
            self.X_straight,
            self.Y_straight,
            image = self.img_forward_tk,
            anchor = tk.CENTER,
            tag = "F_forward"
        )
        self.cvs_forward.tag_bind(
            self.id_forward,
            '<Button-1>',
            lambda e: [self.forward(), self.start_blinking(self.id_forward)]
            #lambda e: [self.change_frame_flag("F"), self.forward(), self.start_blinking(self.id_forward), self.changePage(self.forward_frame)]
            )
        # cw旋回シンボル
        self.id_F_cw = self.cvs_forward.create_image(
            self.X_cw,
            self.Y_cw,
            image = self.img_cw_tk,
            anchor = tk.CENTER,
            tag = "cw"
        )
        self.cvs_forward.tag_bind(
            self.id_F_cw,
            '<Button-1>',
            lambda e: [self.cw(), self.start_blinking(self.id_F_cw)]
            )
        
        # ccw旋回シンボル
        self.id_F_ccw = self.cvs_forward.create_image(
            self.X_ccw,
            self.Y_ccw,
            image = self.img_ccw_tk,
            anchor = tk.CENTER,
            tag = "ccw"
        )
        self.cvs_forward.tag_bind(
            self.id_F_ccw,
            '<Button-1>',
            lambda e: [self.ccw(), self.start_blinking(self.id_F_ccw)]
            )
        
        # 停止シンボル
        self.id_F_stop = self.cvs_forward.create_image(
            self.X_stop,
            self.Y_stop,
            image = self.img_stop_tk,
            anchor = tk.CENTER,
            tag = "stop"
        )
        self.cvs_forward.tag_bind(
            self.id_F_stop,
            '<Button-1>',
            lambda e: [self.change_frame_flag("S_F"), self.stop(), self.changePage(self.stop_forward_frame), self.stop_blink()]
            )
        
        #-----------------------back_frame-------------------------------------
        #後方のフレームを作成
        self.back_frame = ttk.Frame()
        self.back_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_back = tk.Canvas(self.back_frame,width=1275,height=765)
        self.cvs_back.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )

        '''ロックシンボル'''
        # 後退ロック
        self.id_lock_back = self.cvs_back.create_image(
            self.X_straight,
            self.Y_straight,
            image = self.img_lock_back_tk,
            anchor = tk.CENTER,
            tag = "lock_back"
        )

        # cwロック
        self.id_lock_B_cw = self.cvs_back.create_image(
            self.X_cw,
            self.Y_cw,
            image = self.img_lock_cw_tk,
            anchor = tk.CENTER,
            tag = "lock_B_cw"
        )

        # ccwロック
        self.id_lock_B_ccw = self.cvs_back.create_image(
            self.X_ccw,
            self.Y_ccw,
            image = self.img_lock_ccw_tk,
            anchor = tk.CENTER,
            tag = "lock_B_ccw"
        )

        '''ロボット操縦シンボル'''
        # 後退シンボル
        self.id_back = self.cvs_back.create_image(
            self.X_straight,
            self.Y_straight,
            image = self.img_back_tk,
            anchor = tk.CENTER,
            tag = "back"
        )
        self.cvs_back.tag_bind(
            self.id_back,
            '<Button-1>',
            lambda e: [self.back(), self.start_blinking(self.id_back)]
            )
        
        # cw旋回シンボル
        self.id_B_cw = self.cvs_back.create_image(
            self.X_cw,
            self.Y_cw,
            image = self.img_cw_tk,
            anchor = tk.CENTER,
            tag = "B_cw"
        )
        self.cvs_back.tag_bind(
            self.id_B_cw,
            '<Button-1>',  
            lambda e: [self.cw(), self.start_blinking(self.id_B_cw)]
            )

        # ccw旋回シンボル
        self.id_B_ccw = self.cvs_back.create_image(
            self.X_ccw,
            self.Y_ccw,
            image = self.img_ccw_tk,
            anchor = tk.CENTER,
            tag = "B_ccw"
        )
        self.cvs_back.tag_bind(
            self.id_B_ccw,
            '<Button-1>',  
            lambda e: [self.ccw(), self.start_blinking(self.id_B_ccw)]
            )    
        
        # 停止シンボル
        self.id_B_stop = self.cvs_back.create_image(
            self.X_stop,
            self.Y_stop,
            image = self.img_stop_tk,
            anchor = tk.CENTER,
            tag = "B_stop"
        )
        self.cvs_back.tag_bind(
            self.id_B_stop,
            '<Button-1>',
            lambda e: [self.change_frame_flag("S_B"), self.stop(), self.changePage(self.stop_back_frame), self.stop_blink()]
            )
        #--------------------------------------------------------------------------------------------------------

        #メニュー画面を最前面で表示
        self.menu_frame.tkraise()

        ###シンボルフィードバック用のインスタンス変数を設定
        self.blink_state = False # 点滅の状態を制御するフラグ
        self.blinking_img_id = None
        self.blink_job = None


    '''シンボルを透明にする関数'''
    def apply_transparency(self, img, alpha):
        img = img.convert("RGBA")
        datas = img.getdata()

        newData = []
        for item in datas:
            if item[3] > 0:  # シンボル部分のみに透明度を追加
                newData.append((item[0], item[1], item[2], alpha))
            else:
                newData.append((item[0], item[1], item[2], 0)) # 画像余白部分は透明度0（完全に透明）

        img.putdata(newData)
        return img

    '''シンボルサイズのコンフィグレーションファイルを詠み込む関数'''
    def read_config(self, filepath):
        config = {}
        with open(filepath, 'r') as file:
            for line in file:
                name, value = line.strip().split('=')
                config[name] = value
        print(config)
        return config

    '''画像の点滅を開始する関数'''
    def start_blinking(self, img_id):
        self.blink_state = False # 現在の点滅を一時停止
        if self.blink_job is not None: # 既にシンボルが点滅している時
            self.after_cancel(self.blink_job) # 現在のシンボル点滅を停止
        if self.blinking_img_id is not None: # 既に点滅中の画像がある場合
            if self.flag == "F": 
                self.cvs_forward.itemconfigure(self.blinking_img_id, state='normal') #点滅してたシンボルを'表示'状態にして点滅停止
            if self.flag == "B": 
                self.cvs_back.itemconfigure(self.blinking_img_id, state='normal') #点滅してたシンボルを'表示'状態にして点滅停止
        self.blinking_img_id = img_id # self.blinking_img_idをクリックされたシンボルのIDに更新
        self.blink_state = True # クリックされたシンボルで新たに点滅を開始
        self.blink()

    '''画像の点滅を実行する関数'''
    def blink(self):
        if self.blink_state and self.blinking_img_id is not None:
            if self.flag == "F": # 前方走行時
                current_state = self.cvs_forward.itemcget(self.blinking_img_id, 'state') # 点滅させたいシンボルの状態を取得
                # 表示と非表示を繰り返して点滅させる
                if current_state == 'normal': 
                    new_state = 'hidden'
                else:
                    new_state = 'normal'

                self.cvs_forward.itemconfigure(self.blinking_img_id, state = new_state) # シンボルの状態を変更
                self.blink_job = self.after(500, self.blink)# 繰り返し呼び出す

            elif self.flag == "B": # 後方走行時
                current_state = self.cvs_back.itemcget(self.blinking_img_id, 'state') # 点滅させたいシンボルの状態を取得
                # 表示と非表示を繰り返して点滅させる
                if current_state == 'normal': 
                    new_state = 'hidden'
                else:
                    new_state = 'normal'

                self.cvs_back.itemconfigure(self.blinking_img_id, state = new_state) # シンボルの状態を変更
                self.blink_job = self.after(500, self.blink)# 繰り返し呼び出す

    '''画像の点滅を停止する関数'''
    def stop_blink(self):
        self.blink_state = False # 現在の点滅を一時停止
        self.after_cancel(self.blink_job) # 現在のシンボル点滅を停止
        if self.flag == "S_F": 
            self.cvs_forward.itemconfigure(self.blinking_img_id, state='normal') #点滅してたシンボルを'表示'状態にして点滅停止
        if self.flag == "S_B": 
            self.cvs_back.itemconfigure(self.blinking_img_id, state='normal') #点滅してたシンボルを'表示'状態にして点滅停止

    '''1フレーム分のデータを受け取って表示する関数'''
    def disp_image(self):
        '''canvasに画像を表示'''

        #前方カメラか後方カメラどちらかの映像をフラグの状態によって取得
        if self.flag == "F" or self.flag == "S_F" or self.flag == "M_F" or self.flag == "H_F":
            ret, data = self.capture_F.read()
    
        elif self.flag == "B" or self.flag == "S_B" or self.flag == "M_B" or self.flag == "H_B":
            ret, data = self.capture_B.read()            

        # BGR→RGB変換
        cv_image = cv2.cvtColor(data, cv2.COLOR_BGR2RGB)

        # NumPyのndarrayからPillowのImageへ変換
        pil_image = Image.fromarray(cv_image)
        
        #画面のサイズにリサイズ0
        pil_image = pil_image.resize((1275, 765))

        #PIL.ImageからPhotoImageへ変換する
        self.bg = ImageTk.PhotoImage(pil_image)

        #画像描画
        if self.flag == 'F':
            ID_F = self.cvs_forward.create_image(0,0,anchor='nw',image=self.bg, tag = "background")
            self.cvs_forward.tag_lower('background')
        elif self.flag == 'S_F':
            self.cvs_stop_forward.create_image(0,0,anchor='nw',image=self.bg, tag = "background")
            self.cvs_stop_forward.tag_lower('background')
        elif self.flag == 'B':
            ID_B = self.cvs_back.create_image(0,0,anchor='nw',image=self.bg, tag = "background")
            self.cvs_back.tag_lower('background')
        elif self.flag == 'S_B':
            self.cvs_stop_back.create_image(0,0,anchor='nw',image=self.bg, tag = "background")
            self.cvs_stop_back.tag_lower('background')         
        elif self.flag == 'M_F':
            self.cvs_menu.create_image(0,0,anchor='nw',image=self.bg, tag = "background")
            self.cvs_menu.tag_lower('background')
        elif self.flag == 'M_B':
            self.cvs_menu_back.create_image(0,0,anchor='nw',image=self.bg, tag = "background")
            self.cvs_menu_back.tag_lower('background')          
        elif self.flag == 'H_F': # 介助者操縦モードの前方メニュー画面
            self.cvs_menu_helper_F.create_image(0,0,anchor='nw',image=self.bg, tag = "background")
            self.cvs_menu_helper_F.tag_lower('background')
        elif self.flag == 'H_B': # 介助者操縦モードの後方メニュー画面
            self.cvs_menu_helper_B.create_image(0,0,anchor='nw',image=self.bg, tag = "background")
            self.cvs_menu_helper_B.tag_lower('background')            

        #画像更新のために10msスレッドを空ける
        self.after(10, self.disp_image)

    '''フレームごとで映像を表示し続けるために、フラグを変更する関数'''
    def change_frame_flag(self, frame_flag):
        self.flag = frame_flag

    '''画面遷移用の関数'''
    def changePage(self, page):
        self.arg = True
        page.tkraise()   #指定のフレームを最前面に移動

    '''シンボルロック・アンロック用の関数'''
    
    def lock_symbol(self):
        if not msg_q.empty(): # 障害物情報に変化があったとき
            laser_msg = msg_q.get(block=True, timeout=True)
            self.delete_and_paste(laser_msg)
            self.str = laser_msg # 遷移後の画面でもシンボルロックするために前回の障害物情報を保持
            msg_q.task_done()

        if self.arg == True:  # 画面遷移が行われたとき
            self.delete_and_paste(self.str)
            self.arg = False
        self.after(10, self.lock_symbol)

    '''シンボルを貼りかえる関数'''
    def delete_and_paste(self, laser_msg):
        if self.flag == 'S_F': # 前方停止画面のとき

            # 前進シンボルの処理
            
            if laser_msg[1] == True:
                self.cvs_stop_forward.itemconfigure(self.id_S_F_forward, state = 'hidden') # 前進シンボルを非表示
                self.cvs_stop_forward.itemconfigure(self.id_lock_S_F_forward, state = 'normal') # 前進ロックシンボルを表示
            else:
                self.cvs_stop_forward.itemconfigure(self.id_S_F_forward, state = 'normal') # 前進シンボルを表示
                self.cvs_stop_forward.itemconfigure(self.id_lock_S_F_forward, state = 'hidden') # 前進ロックシンボルを非表示

            # cw旋回シンボルの処理
            if laser_msg[3] == True:
                self.cvs_stop_forward.itemconfigure(self.id_S_F_cw, state = 'hidden') # cw旋回シンボルを非表示
                self.cvs_stop_forward.itemconfigure(self.id_lock_S_F_cw, state = 'normal') # cw旋回ロックシンボルを表示
            else:
                self.cvs_stop_forward.itemconfigure(self.id_S_F_cw, state = 'normal') # cw旋回シンボルを表示
                self.cvs_stop_forward.itemconfigure(self.id_lock_S_F_cw, state = 'hidden') # cw旋回シンボルを非表示

            # ccw旋回シンボルの処理
            if laser_msg[9] == True:
                self.cvs_stop_forward.itemconfigure(self.id_S_F_ccw, state = 'hidden') # ccw旋回シンボルを非表示
                self.cvs_stop_forward.itemconfigure(self.id_lock_S_F_ccw, state = 'normal') # ccw旋回ロックシンボルを表示
            else:
                self.cvs_stop_forward.itemconfigure(self.id_S_F_ccw, state = 'normal') # ccw旋回シンボルを表示
                self.cvs_stop_forward.itemconfigure(self.id_lock_S_F_ccw, state = 'hidden') # ccw旋回シンボルを非表示       

        elif self.flag == 'S_B': # 後方停止画面のとき
            # 後退シンボルの処理
            if laser_msg[6] == True:
                self.cvs_stop_back.itemconfigure(self.id_S_B_back, state = 'hidden') # 後退移動シンボルを非表示
                self.cvs_stop_back.itemconfigure(self.id_lock_S_B_back, state = 'normal') # 後退ロックシンボルを表示
            else:
                self.cvs_stop_back.itemconfigure(self.id_S_B_back, state = 'normal') # 後退シンボルを表示
                self.cvs_stop_back.itemconfigure(self.id_lock_S_B_back, state = 'hidden') # 後退ロックシンボルを非表示

            # cw旋回シンボルの処理
            if laser_msg[3] == True:
                self.cvs_stop_back.itemconfigure(self.id_S_B_cw, state = 'hidden') # cw旋回シンボルを非表示
                self.cvs_stop_back.itemconfigure(self.id_lock_S_B_cw, state = 'normal') # cw旋回ロックシンボルを表示
            else:
                self.cvs_stop_back.itemconfigure(self.id_S_B_cw, state = 'normal') # cw旋回シンボルを表示
                self.cvs_stop_back.itemconfigure(self.id_lock_S_B_cw, state = 'hidden') # cw旋回ロックシンボルを非表示

            # ccw旋回シンボルの処理
            if laser_msg[9] == True:
                self.cvs_stop_back.itemconfigure(self.id_S_B_ccw, state = 'hidden') # ccw旋回シンボルを非表示
                self.cvs_stop_back.itemconfigure(self.id_lock_S_B_ccw, state = 'normal') # ccw旋回ロックシンボルを表示
            else:
                self.cvs_stop_back.itemconfigure(self.id_S_B_ccw, state = 'normal') # ccw旋回シンボルを表示
                self.cvs_stop_back.itemconfigure(self.id_lock_S_B_ccw, state = 'hidden') # ccw旋回ロックシンボルを非表示

        elif self.flag == 'F': # 前方走行中画面のとき
            # 直進シンボルの処理
            if laser_msg[1] == True:
                self.cvs_forward.itemconfigure(self.id_forward, state = 'hidden') # 直進シンボルを非表示
                self.cvs_forward.itemconfigure(self.id_lock_forward, state = 'normal') # 直進ロックシンボルを表示
            else:
                self.cvs_forward.itemconfigure(self.id_forward, state = 'normal') # 直進シンボルを表示
                self.cvs_forward.itemconfigure(self.id_lock_forward, state = 'hidden') # 直進ロックシンボルを非表示            

            # cw旋回シンボルの処理
            if laser_msg[3] == True:
                self.cvs_forward.itemconfigure(self.id_F_cw, state = 'hidden') # cw旋回シンボルを非表示
                self.cvs_forward.itemconfigure(self.id_lock_F_cw, state = 'normal') # cw旋回ロックシンボルを表示
            else:
                self.cvs_forward.itemconfigure(self.id_F_cw, state = 'normal') # cw旋回シンボルを表示
                self.cvs_forward.itemconfigure(self.id_lock_F_cw, state = 'hidden') # cw旋回ロックシンボルを非表示

            # ccw旋回シンボルの処理
            if laser_msg[9] == True:
                self.cvs_forward.itemconfigure(self.id_F_ccw, state = 'hidden') # ccw旋回シンボルを非表示
                self.cvs_forward.itemconfigure(self.id_lock_F_ccw, state = 'normal') # ccw旋回ロックシンボルを表示
            else:
                self.cvs_forward.itemconfigure(self.id_F_ccw, state = 'normal') # ccw旋回シンボルを表示
                self.cvs_forward.itemconfigure(self.id_lock_F_ccw, state = 'hidden') # ccw旋回ロックシンボルを非表示

        elif self.flag == 'B': # 後方走行中画面のとき
            # 後退シンボルの処理
            if laser_msg[6] == True:
                self.cvs_back.itemconfigure(self.id_back, state = 'hidden') # 後退シンボルを非表示
                self.cvs_back.itemconfigure(self.id_lock_back, state = 'normal') # 後退ロックシンボルを表示
            else:
                self.cvs_back.itemconfigure(self.id_back, state = 'normal') # 後退シンボルを表示
                self.cvs_back.itemconfigure(self.id_lock_back, state = 'hidden') # 後退ロックシンボルを非表示

            # cw旋回シンボルの処理
            if laser_msg[3] == True:
                self.cvs_back.itemconfigure(self.id_B_cw, state = 'hidden') # cw旋回シンボルを非表示
                self.cvs_back.itemconfigure(self.id_lock_B_cw, state = 'normal') # cw旋回ロックシンボルを表示
            else:
                self.cvs_back.itemconfigure(self.id_B_cw, state = 'normal') # cw旋回シンボルを表示
                self.cvs_back.itemconfigure(self.id_lock_B_cw, state = 'hidden') # cw旋回ロックシンボルを非表示

            # ccw旋回シンボルの処理
            if laser_msg[9] == True:
                self.cvs_back.itemconfigure(self.id_B_ccw, state = 'hidden') # ccw旋回シンボルを非表示
                self.cvs_back.itemconfigure(self.id_lock_B_ccw, state = 'normal') # ccw旋回ロックシンボルを表示
            else:
                self.cvs_back.itemconfigure(self.id_B_ccw, state = 'normal') # ccw旋回シンボルを表示
                self.cvs_back.itemconfigure(self.id_lock_B_ccw, state = 'hidden') # ccw旋回ロックシンボルを非表示

    '''衝突防止動作によって停止画面に遷移させるかを判断する関数'''
    def determine_transition(self):
        global state_flag
        if not state_q.empty():
            state_msg = state_q.get(block=True, timeout=True)
            if not state_msg:
                if self.flag == "F":
                    self.changePage(self.stop_forward_frame)
                    self.change_frame_flag("S_F")
                elif self.flag == "B":
                    self.changePage(self.stop_back_frame)
                    self.change_frame_flag("S_B")
            state_q.task_done()
        
        self.after(10, self.determine_transition)

    '''文字列送信用の関数'''
    def control(self, data):
        #print("GUIデバッグ中")
        #'''
        HOST='192.168.1.102'
        PORT=12345
        BUFFER=4096
            # Define socket communication type ipv4, tcp
        self.soc=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            #connect to the server 
        self.soc.connect((HOST,PORT))
            #delay
        #time.sleep(1)
        if data == "exit":
            pass
        else:
            try:
                self.soc.send(data.encode("utf-8"))
            except ConnectionResetError:
                pass
        buf=self.soc.recv(BUFFER)
        #'''

    '''configファイル送信用の関数'''
    def send_config(self, file_path, host, port):
        # サーバに接続
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))

            # ファイルを開いて送信
            with open(file_path, 'rb') as file:
                data = file.read()
                s.sendall(data)
            print("ファイル送信完了")

    '''走行指令送信の関数達'''
    def forward(self):
        print("前進")
        self.control("w")

    def back(self):
        print("後退")
        self.control("x")

    def cw(self):
        print("cw旋回")
        self.control("d")

    def ccw(self):
        print("ccw旋回")
        self.control("a")

    def stop(self):
        print("停止")
        self.control("s")

    def helper(self):
        print("介助者操縦モード")
        global mode_flag
        mode_flag = False
        self.control("helper")

    def user(self):
        print("ユーザ操縦モード")
        global mode_flag
        mode_flag = True
        self.control("user")

    def menu(self):
        global mode_flag
        if mode_flag:
            print("ユーザ操縦モードのメニュー画面へ")
            if self.flag =='S_F':
                self.changePage(self.menu_frame)
                self.change_frame_flag("M_F")
            else:
                self.changePage(self.menu_back_frame)
                self.change_frame_flag("M_B")
        else:
            print("介助者操縦モードのメニュー画面へ")
            if self.flag == 'S_F':
                self.changePage(self.menu_helper_F_frame)
                self.change_frame_flag("H_F")
            else:
                self.changePage(self.menu_helper_B_frame)
                self.change_frame_flag("H_B")

    '''後方走行時 → メニュー画面 → 走行開始 を選んだ場合も後方カメラ映像を映すための関数'''
    def start_running(self):
        print("走行開始")
        self.control("run")
        if self.flag == "M_F" or self.flag == "H_F":
            self.arg = True
            self.stop_forward_frame.tkraise()
            self.change_frame_flag("S_F")
        elif self.flag == "M_B" or self.flag == "H_B":
            self.arg = True
            self.stop_back_frame.tkraise()
            self.change_frame_flag("S_B")

    '''終了の関数'''
    def Finish(self):
        print("終了")
        
        self.control("f")
        self.soc.close()
        if client_socket:
            client_socket.close()
        if client_socket_s:
            client_socket_s.close()
        
        self.destroy()#destroy()クラスメソッドでtkinterウィンドウを閉じる
        sys.exit()

'''ロボットの状態を受け取る関数'''
def receive_state_data():
    global client_socket_s
    while True:
        try:
            server_address_s = ('192.168.1.102', 50010)
            client_socket_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket_s.connect(server_address_s)
            received_data_s = client_socket_s.recv(1)
            bool_value = struct.unpack('?', received_data_s)[0]
            print("ロボットの状態", bool_value)
            #state_flag = bool_value
            state_q.put(bool_value)
            state_q.join()
        except EOFError:
            continue

'''周辺障害物の情報を受け取る関数'''
def receive_laser_data():
    global client_socket
    while True:
        try:
            server_address = ('192.168.1.102', 50000)
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(server_address)
            received_data = client_socket.recv(1024)  # データの受信
            array = pickle.loads(received_data)
            msg_q.put(array)
            msg_q.join()
        except EOFError:
            continue 

if __name__ == "__main__":
    root = MyApp()
    #'''
    thread2 = threading.Thread(target=receive_laser_data)
    thread2.start()
    thread3 = threading.Thread(target=receive_state_data)
    thread3.start()
    #'''
    root.disp_image()
    root.lock_symbol()
    root.determine_transition()
    
    root.mainloop()