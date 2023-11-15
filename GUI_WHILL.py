# cv2のインポート前にカメラに関する設定を行う
import os
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"
import pickle
import socket
#from tkinter import *
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageOps
import cv2, numpy, time, csv, sys, struct
import threading, multiprocessing, queue
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
#Set server ip address, port, buffer capacity

q = queue.Queue()       #受信する画像データをスレッド間で共有するためのキュー

msg_q = queue.Queue()   #障害物情報を保持するキュー
#str_q = queue.Queue()   #画面遷移時に障害物情報を用いるときのキュー

state_q = queue.Queue()

img_flag = 'M_F'   #前方カメラか後方カメラ、どちらを受け取る画像データにするか判断するための変数（F：前方、B：後方、M：Menu、S：停止中）

time_start = 0

state_flag = False   #衝突防止動作によってロボットが停止したかどうかを判断するブール値(False：停止, True：動作中)

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

        self.flag = 'M_F'   #フレームごとで映像を表示するためのフラグ

        self.str = [False, False, False, False]   #前回の障害物情報用、初期値は周りに障害物なしとみなす

        self.arg = False   #画面遷移したかどうか

        self.str_state = False   #衝突防止動作の実行前にロボットが動いていたかを判断する

        # 前方、後方カメラをオープンする
        self.capture_F = cv2.VideoCapture(1)
        self.capture_B = cv2.VideoCapture(2)   

        '''シンボル画像用意'''
        #走行開始シンボル
        self.img_start = Image.open('start.png')
        self.img_start = self.img_start.resize((250, 150))
        self.img_start = ImageTk.PhotoImage(self.img_start)
        #後方の走行開始シンボル
        self.img_start_back = Image.open('start_back.png')
        self.img_start_back = self.img_start_back.resize((250, 150))
        self.img_start_back = ImageTk.PhotoImage(self.img_start_back)
        #終了シンボル
        self.img_finish = Image.open('finish_letter.png')
        self.img_finish = self.img_finish.resize((150, 100))
        self.img_finish = ImageTk.PhotoImage(self.img_finish)       
        #前方向への画面遷移シンボル
        self.img_change_forward = Image.open('change_forward.png')
        self.img_change_forward = self.img_change_forward.resize((200, 100))
        self.img_change_forward = ImageTk.PhotoImage(self.img_change_forward)
        #後ろ方向への画面遷移シンボル
        self.img_change_back = Image.open('change_back.png')
        self.img_change_back = self.img_change_back.resize((200, 100))
        self.img_change_back = ImageTk.PhotoImage(self.img_change_back)
        #メニューへの画面遷移シンボル
        self.img_menu = Image.open('menu.png')
        self.img_menu = self.img_menu.resize((200, 100))
        self.img_menu = ImageTk.PhotoImage(self.img_menu) 
        #前進シンボル
        self.img_forward = Image.open('forward_3d.png')
        self.img_forward = self.img_forward.resize((200, 100))
        self.img_forward = ImageTk.PhotoImage(self.img_forward)
        #停止シンボル
        self.img_stop = Image.open('stop_3d.png')
        self.img_stop = self.img_stop.resize((200, 200))
        self.img_stop = ImageTk.PhotoImage(self.img_stop)
        #cw旋回シンボル
        self.img_cw = Image.open('cw_3d.png')
        self.img_cw = self.img_cw.resize((150, 200))
        self.img_cw = ImageTk.PhotoImage(self.img_cw)
        #ccwシンボル
        self.img_ccw = Image.open('ccw_3d.png')
        self.img_ccw = self.img_ccw.resize((150, 200))
        self.img_ccw = ImageTk.PhotoImage(self.img_ccw)
        ###シンボル作成###
        #後退シンボル
        self.img_back = Image.open('back_3d.png')
        self.img_back = self.img_back.resize((200, 100))
        self.img_back = ImageTk.PhotoImage(self.img_back)
        ######
        #前進ロックシンボル
        self.img_forward_lock = Image.open('forward_3d_lock.png')
        self.img_forward_lock = self.img_forward_lock.resize((200, 100))
        self.img_forward_lock = ImageTk.PhotoImage(self.img_forward_lock)
        #cw旋回ロックシンボル
        self.img_cw_lock = Image.open('cw_3d_lock.png')
        self.img_cw_lock = self.img_cw_lock.resize((150, 200))
        self.img_cw_lock = ImageTk.PhotoImage(self.img_cw_lock)
        #ccw旋回ロックシンボル
        self.img_ccw_lock = Image.open('ccw_3d_lock.png')
        self.img_ccw_lock = self.img_ccw_lock.resize((150, 200))
        self.img_ccw_lock = ImageTk.PhotoImage(self.img_ccw_lock)
        #後退ロックシンボル
        self.img_back_lock = Image.open('back_3d_lock.png')
        self.img_back_lock = self.img_back_lock.resize((200, 100))
        self.img_back_lock = ImageTk.PhotoImage(self.img_back_lock)  
        #警告シンボル
        self.img_warning = Image.open('warning.png')
        self.img_warning = self.img_warning.resize((100, 100))
        self.img_warning = ImageTk.PhotoImage(self.img_warning)      
        ######
        
#-----------------------------menu_frame------------------------------

        #前方画面フレーム作成
        self.menu_frame = ttk.Frame()
        self.menu_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_menu = tk.Canvas(self.menu_frame,width=1275,height=765)
        self.cvs_menu.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )

        #走行開始ボタン
        self.button_start = tk.Button(
            self.menu_frame,
            image=self.img_start,
            command= self.start_running
        )
        #貼り付け
        self.button_start.place(
            x = 637,
            y = 280,
            width=240,
            height=145,
            anchor=tk.CENTER
        )

        #終了ボタン
        self.button_finish = tk.Button(
            self.menu_frame,
            image=self.img_finish,
            command=self.Finish
        )
        #貼り付け
        self.button_finish.place(
            x = 1195,
            y = 720,
            width=150,
            height=110,
            anchor=tk.CENTER
        )

        self.cvs_menu.create_image(50, 552, image = self.img_warning, anchor = tk.CENTER)
#------------------------------------------------------------------------
#-----------------------------menu_back_frame------------------------------

        #後方メニューフレーム作成
        self.menu_back_frame = ttk.Frame()
        self.menu_back_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_menu_back = tk.Canvas(self.menu_back_frame,width=1275,height=765)
        self.cvs_menu_back.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )

        #後方の走行開始ボタン
        self.button_start_back = tk.Button(
            self.menu_back_frame,
            image=self.img_start_back,
            command= self.start_running
        )
        #貼り付け
        self.button_start_back.place(
            x = 637,
            y = 280,
            width=240,
            height=145,
            anchor=tk.CENTER
        )

        #終了ボタン
        self.button_finish = tk.Button(
            self.menu_back_frame,
            image=self.img_finish,
            command=self.Finish
        )
        #貼り付け
        self.button_finish.place(
            x = 1195,
            y = 720,
            width=150,
            height=110,
            anchor=tk.CENTER
        )
#-----------------------------forward_frame------------------------------

        #前方画面フレーム作成
        self.forward_frame = ttk.Frame()
        self.forward_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_forward = tk.Canvas(self.forward_frame,width=1275,height=765)
        self.cvs_forward.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )

        ###ボタン設置###
        #前進ボタン
        self.button_forward = tk.Button(
            self.forward_frame,
            image=self.img_forward,
            command=self.forward
        )
        #貼り付け
        self.button_forward.place(
            x = 637,
            y = 50,
            anchor=tk.CENTER
        )

        #停止ボタン
        self.button_stop = tk.Button(
            self.forward_frame,
            image=self.img_stop,
            command=lambda : [self.changePage(self.stop_forward_frame), self.change_frame_flag("S_F"), self.stop()]
        )
        #貼り付け
        self.button_stop.place(
            x = 337,
            y = 660,
            width=200,
            height=200,
            anchor=tk.CENTER
        )

        #cw旋回ボタン
        self.button_f_cw = tk.Button(
            self.forward_frame,
            image=self.img_cw,
            command=self.cw
        )
        #貼り付け
        self.button_f_cw.place(
            x = 1185,
            y = 382,
            width=150,
            height=200,
            anchor=tk.CENTER
        )

        #ccw旋回ボタン
        self.button_f_ccw = tk.Button(
            self.forward_frame,
            image=self.img_ccw,
            command=self.ccw
        )
        #貼り付け
        self.button_f_ccw.place(
            x = 67,
            y = 382,
            width=150,
            height=200,
            anchor=tk.CENTER
        )

        #前方操作画面の前進ロックボタン
        self.button_forward_lock = tk.Button(
            self.forward_frame,
            image=self.img_forward_lock,
        )

        #前方操作画面のcw旋回ロックボタン
        self.button_f_cw_lock = tk.Button(
            self.forward_frame,
            image=self.img_cw_lock,
        )

        #前方操作画面のccw旋回ロックボタン
        self.button_f_ccw_lock = tk.Button(
            self.forward_frame,
            image=self.img_ccw_lock,
        )

        #警告シンボル
        self.img_ID_0 = self.cvs_forward.create_image(50, 50, image = self.img_warning, anchor = tk.CENTER)
        self.img_ID_2 = self.cvs_forward.create_image(1220, 50, image = self.img_warning, anchor = tk.CENTER)
        self.img_ID_4 = self.cvs_forward.create_image(1220, 222, image = self.img_warning, anchor = tk.CENTER)
        self.img_ID_10 = self.cvs_forward.create_image(50, 222, image = self.img_warning, anchor = tk.CENTER)
#----------------------------------------------------------------------
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

        ###ボタン設置###
        '''ロボット操作ボタン'''
        #停止画面の前進ボタン
        self.button_stop_forward = tk.Button(
            self.stop_forward_frame,
            image=self.img_forward,
            command=lambda : [self.changePage(self.forward_frame), self.change_frame_flag("F"), self.forward()]
        )
        #貼り付け
        self.button_stop_forward.place(
            x = 637,
            y = 50,
            anchor=tk.CENTER
        )

        #前方停止画面のcw旋回ボタン
        self.button_stop_f_cw = tk.Button(
            self.stop_forward_frame,
            image=self.img_cw,
            command=lambda : [self.changePage(self.forward_frame), self.change_frame_flag("F"), self.cw()]
        )
        #貼り付け
        self.button_stop_f_cw.place(
            x = 1185,
            y = 382,
            width=150,
            height=200,
            anchor=tk.CENTER
        )

        #前方停止画面のccw旋回ボタン
        self.button_stop_f_ccw = tk.Button(
            self.stop_forward_frame,
            image=self.img_ccw,
            command=lambda : [self.changePage(self.forward_frame), self.change_frame_flag("F"), self.ccw()]
        )
        #貼り付け
        self.button_stop_f_ccw.place(
            x = 67,
            y = 382,
            width=150,
            height=200,
            anchor=tk.CENTER
        )
        ''''''
        '''ロックボタン'''
        #停止画面の前進ロックボタン
        self.button_stop_forward_lock = tk.Button(
            self.stop_forward_frame,
            image=self.img_forward_lock,
        )

        #前方停止画面のcw旋回ロックボタン
        self.button_stop_f_cw_lock = tk.Button(
            self.stop_forward_frame,
            image=self.img_cw_lock,
        )

        #前方停止画面のccw旋回ロックボタン
        self.button_stop_f_ccw_lock = tk.Button(
            self.stop_forward_frame,
            image=self.img_ccw_lock,
        )

        ''''''
        '''ロボット操作以外のボタン'''
        #後方画面に遷移するボタン
        self.button_change_back_frame = tk.Button(
            self.stop_forward_frame,
            image=self.img_change_back,
            command=lambda : [self.changePage(self.stop_back_frame), self.change_frame_flag("S_B")]
        )
        #貼り付け
        self.button_change_back_frame.place(
            x =1150,
            y = 682,
            anchor=tk.CENTER
        )
        #メニューへのボタン
        self.button_menu = tk.Button(
            self.stop_forward_frame,
            image=self.img_menu,
            command=lambda : [self.changePage(self.menu_frame), self.change_frame_flag("M_F")]
        )
        #貼り付け
        self.button_menu.place(
            x = 110,
            y = 682,
            width=190,
            height=100,
            anchor=tk.CENTER
        )
        ''''''
#--------------------------------------------------------------------------------------------------------
#------------------------------------back_frame---------------------------------------------------------
        #後方画面フレーム作成
        self.back_frame = ttk.Frame()
        self.back_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_back = tk.Canvas(self.back_frame,width=1275,height=765)
        self.cvs_back.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )

        ###ボタン設置###
        #後進ボタン
        self.button_back = tk.Button(
            self.back_frame,
            image=self.img_back,
            command=self.back
        )
        #貼り付け
        self.button_back.place(
            x = 637,
            y = 50,
            anchor=tk.CENTER
        )

        #停止ボタン
        self.button_stop = tk.Button(
            self.back_frame,
            image=self.img_stop,
            command=lambda : [self.changePage(self.stop_back_frame), self.change_frame_flag("S_B"), self.stop()]
        )
        #貼り付け
        self.button_stop.place(
            x = 337,
            y = 660,
            width=200,
            height=200,
            anchor=tk.CENTER
        )

        #cw旋回ボタン
        self.button_b_cw = tk.Button(
            self.back_frame,
            image=self.img_cw,
            command=self.cw
        )
        #貼り付け
        self.button_b_cw.place(
            x = 1185,
            y = 382,
            width=150,
            height=200,
            anchor=tk.CENTER
        )

        #ccw旋回ボタン
        self.button_b_ccw = tk.Button(
            self.back_frame,
            image=self.img_ccw,
            command=self.ccw
        )
        #貼り付け
        self.button_b_ccw.place(
            x = 67,
            y = 382,
            width=150,
            height=200,
            anchor=tk.CENTER
        )

        #後方操作画面の後退ロックボタン
        self.button_back_lock = tk.Button(
            self.back_frame,
            image=self.img_back_lock,
        )

        #後方操作画面のcw旋回ロックボタン
        self.button_b_cw_lock = tk.Button(
            self.back_frame,
            image=self.img_cw_lock,
        )

        #後方操作画面のccw旋回ロックボタン
        self.button_b_ccw_lock = tk.Button(
            self.back_frame,
            image=self.img_ccw_lock,
        )

        #後方操作画面の警告シンボル
        self.img_ID_4_B = self.cvs_back.create_image(50, 552, image = self.img_warning, anchor = tk.CENTER)
        self.img_ID_6_B = self.cvs_back.create_image(50, 50, image = self.img_warning, anchor = tk.CENTER)
        self.img_ID_8_B = self.cvs_back.create_image(1220, 50, image = self.img_warning, anchor = tk.CENTER)
        self.img_ID_10_B = self.cvs_back.create_image(1220, 552, image = self.img_warning, anchor = tk.CENTER)
#----------------------------------------------------------------------
#-----------------------stop_back_frame-------------------------------------
        #後方走行中の停止時フレームを作成
        self.stop_back_frame = ttk.Frame()
        self.stop_back_frame.grid(row=0, column=0, sticky="nsew")

        ###背景画像用のキャンバス###
        self.cvs_stop_back = tk.Canvas(self.stop_back_frame,width=1275,height=765)
        self.cvs_stop_back.place(
            relx=0,
            rely=0,
            bordermode=tk.OUTSIDE
        )

        ###ボタン設置###
        '''ロボット操作ボタン'''
        #停止中の後進ボタン
        self.button_stop_back = tk.Button(
            self.stop_back_frame,
            image=self.img_back,
            command=lambda : [self.changePage(self.back_frame), self.change_frame_flag("B"), self.back()]
        )
        #貼り付け
        self.button_stop_back.place(
            x = 637,
            y = 50,
            anchor=tk.CENTER
        )

        #後方停止画面のcw旋回ボタン
        self.button_stop_b_cw = tk.Button(
            self.stop_back_frame,
            image=self.img_cw,
            command=lambda : [self.changePage(self.back_frame), self.change_frame_flag("B"), self.cw()]
        )
        #貼り付け
        self.button_stop_b_cw.place(
            x = 1185,
            y = 382,
            width=150,
            height=200,
            anchor=tk.CENTER
        )

        #前方停止画面のccw旋回ボタン
        self.button_stop_b_ccw = tk.Button(
            self.stop_back_frame,
            image=self.img_ccw,
            command=lambda : [self.changePage(self.back_frame), self.change_frame_flag("B"), self.ccw()]
        )
        #貼り付け
        self.button_stop_b_ccw.place(
            x = 67,
            y = 382,
            width=150,
            height=200,
            anchor=tk.CENTER
        )
        ''''''
        '''ロックボタン'''
        #停止画面の後退ロックボタン
        self.button_stop_back_lock = tk.Button(
            self.stop_back_frame,
            image=self.img_back_lock,
        )

        #後方停止画面のcw旋回ロックボタン
        self.button_stop_b_cw_lock = tk.Button(
            self.stop_back_frame,
            image=self.img_cw_lock,
        )

        #後方停止画面のccw旋回ロックボタン
        self.button_stop_b_ccw_lock = tk.Button(
            self.stop_back_frame,
            image=self.img_ccw_lock,
        )
        ''''''
        '''ロボット操作以外のボタン'''
        #前方停止画面に遷移するボタン
        self.button_change_forward_frame = tk.Button(
            self.stop_back_frame,
            image=self.img_change_forward,
            command=lambda : [self.changePage(self.stop_forward_frame), self.change_frame_flag("S_F")]
        )
        #貼り付け
        self.button_change_forward_frame.place(
            x = 950,
            y = 682,
            anchor=tk.CENTER
        )
        #後方メニューへのボタン
        self.button_menu = tk.Button(
            self.stop_back_frame,
            image=self.img_menu,
            command=lambda : [self.changePage(self.menu_back_frame), self.change_frame_flag("M_B")]
        )
        #貼り付け
        self.button_menu.place(
            x = 110,
            y = 682,
            width=190,
            height=100,
            anchor=tk.CENTER
        )
        ''''''
#--------------------------------------------------------------------------------------------------------

        #メニュー画面を最前面で表示
        self.menu_frame.tkraise()
        
                   
    '''1フレーム分のデータを受け取って表示する'''
    def disp_image(self):
        global img_flag 
        '''canvasに画像を表示'''

        #前方カメラか後方カメラどちらかの映像をフラグの状態によって取得
        if img_flag == "F" or img_flag == "S_F" or img_flag == "M_F":
            ret, data = self.capture_F.read()
    
        elif img_flag == "B" or img_flag == "S_B" or img_flag == "M_B":
            ret, data = self.capture_B.read()            

        # BGR→RGB変換
        cv_image = cv2.cvtColor(data, cv2.COLOR_BGR2RGB)

        # NumPyのndarrayからPillowのImageへ変換
        pil_image = Image.fromarray(cv_image)
        
        #画面のサイズにリサイズ
        pil_image = pil_image.resize((1275, 765))

        #PIL.ImageからPhotoImageへ変換する
        self.bg = ImageTk.PhotoImage(pil_image)

        #画像描画
        if self.flag == 'F':
            ID_F = self.cvs_forward.create_image(0,0,anchor='nw',image=self.bg)
            self.cvs_forward.tag_lower(ID_F)
        elif self.flag == 'S_F':
            self.cvs_stop_forward.create_image(0,0,anchor='nw',image=self.bg)
        elif self.flag == 'B':
            ID_B = self.cvs_back.create_image(0,0,anchor='nw',image=self.bg)
            self.cvs_back.tag_lower(ID_B)
        elif self.flag == 'S_B':
            self.cvs_stop_back.create_image(0,0,anchor='nw',image=self.bg)         
        elif self.flag == 'M_F':
            self.cvs_menu.create_image(0,0,anchor='nw',image=self.bg)
        elif self.flag == 'M_B':
            self.cvs_menu_back.create_image(0,0,anchor='nw',image=self.bg)          
            
            #画像更新のために10msスレッドを空ける
        self.after(10, self.disp_image)

    
    '''文字列送信用'''
    def control(self, data):
        #time_sta = time.perf_counter()

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
        
        #time_end = time.perf_counter()
        #tim = time_end - time_sta
        #print(tim)

        #print(buf)

    '''ボタンごとの文字列を文字列送信用の関数controlに送る関数たち'''
    #ボタンforward
    def forward(self):
        print("前進")
        self.control("w")
    #ボタンright
    def cw(self):
        print("右旋回")
        self.control("d")
    #ボタンforward
    def ccw(self):
        print("左旋回")
        self.control("a")
    #ボタンstop
    def stop(self):
        print("停止")
        self.control("s")
    #ボタンback
    def back(self):
        print("後進")
        self.control("x")
    '''後方走行時 → メニュー画面 → 走行開始 を選んだ場合も後方カメラ映像を映すための関数'''
    def start_running(self):
        print("走行開始")
        #self.control("run")
        if self.flag == "M_F":
            self.arg = True
            self.stop_forward_frame.tkraise()
            self.change_frame_flag("S_F")
        elif self.flag == "M_B":
            self.arg = True
            self.stop_back_frame.tkraise()
            self.change_frame_flag("S_B")

    '''フレームごとで映像を表示し続けるために、フラグを変更する関数'''
    def change_frame_flag(self, frame_flag):
        global img_flag

        self.flag = frame_flag
        img_flag = frame_flag

    '''画面遷移用の関数'''
    def changePage(self, page):
        self.arg = True
        page.tkraise()   #指定のフレームを最前面に移動

    '''終了の関数'''
    def Finish(self):
        self.control("q")
        self.soc.close()
        #destroy()クラスメソッドでtkinterウィンドウを閉じる
        self.destroy()
        sys.exit()

    '''ボタンを貼り変える関数'''
    def delete_and_paste(self, laser_msg):
        if self.flag == 'F':   #ユーザが前方操作画面を操作している時
            '''前進ボタンの処理'''
            if laser_msg[1] == True:
                #ボタン変更
                self.button_forward.place_forget()
                #貼り付け
                self.button_forward_lock.place(
                    x = 637,
                    y = 50,
                    anchor=tk.CENTER
                )
            elif laser_msg[1] == False:
                #ボタン変更
                self.button_forward_lock.place_forget()
                
                #貼り付け
                self.button_forward.place(
                    x = 637,
                    y = 50,
                    anchor=tk.CENTER
                )
            ''''''
            '''cw旋回ボタンの処理'''
            if laser_msg[3] or laser_msg[5]:
                #ボタン変更
                self.button_f_cw.place_forget()
                #貼り付け
                self.button_f_cw_lock.place(
                    x = 1185,
                    y = 382,
                    anchor=tk.CENTER
                )
                
            elif not laser_msg[3] and not laser_msg[5]:
                #ボタン変更
                self.button_f_cw_lock.place_forget()
                #貼り付け
                self.button_f_cw.place(
                    x = 1185,
                    y = 382,
                    anchor=tk.CENTER
                )
            ''''''
            '''ccw旋回ボタンの処理'''
            if laser_msg[9] or laser_msg[11]:
                #ボタン変更
                self.button_f_ccw.place_forget()
                #貼り付け
                self.button_f_ccw_lock.place(
                    x = 67,
                    y = 382,
                    anchor=tk.CENTER
                )
                
            elif not laser_msg[9] and not laser_msg[11]:
                #ボタン変更
                self.button_f_ccw_lock.place_forget()
                #貼り付け
                self.button_f_ccw.place(
                    x = 67,
                    y = 382,
                    anchor=tk.CENTER
                )
            ''''''
        elif self.flag == 'S_F':   #ユーザが前方停止画面を操作している時
            '''前進ボタンの処理'''
            if laser_msg[1] == True:
                #ボタン変更
                self.button_stop_forward.place_forget()
                #貼り付け
                self.button_stop_forward_lock.place(
                    x = 637,
                    y = 50,
                    anchor=tk.CENTER
                )
                
            elif laser_msg[1] == False:
                #ボタン変更
                self.button_stop_forward_lock.place_forget()
                
                #貼り付け
                self.button_stop_forward.place(
                    x = 637,
                    y = 50,
                    anchor=tk.CENTER
                )
            ''''''
            '''cw旋回ボタンの処理'''
            if laser_msg[3] or laser_msg[5]:
                #ボタン変更
                self.button_stop_f_cw.place_forget()
                #貼り付け
                self.button_stop_f_cw_lock.place(
                    x = 1185,
                    y = 382,
                    anchor=tk.CENTER
                )
                
            elif not laser_msg[3] and not laser_msg[5]:
                #ボタン変更
                self.button_stop_f_cw_lock.place_forget()
                #貼り付け
                self.button_stop_f_cw.place(
                    x = 1185,
                    y = 382,
                    anchor=tk.CENTER
                )
            ''''''
            '''ccw旋回ボタンの処理'''
            if laser_msg[9] or laser_msg[11]:
                #ボタン変更
                self.button_stop_f_ccw.place_forget()
                #貼り付け
                self.button_stop_f_ccw_lock.place(
                    x = 67,
                    y = 382,
                    anchor=tk.CENTER
                )
                
            elif not laser_msg[9] and not laser_msg[11]:
                #ボタン変更
                self.button_stop_f_ccw_lock.place_forget()
                #貼り付け
                self.button_stop_f_ccw.place(
                    x = 67,
                    y = 382,
                    anchor=tk.CENTER
                )
            ''''''
        elif self.flag == 'B':   #ユーザが後方停止画面を操作している時
            '''後退ボタンの処理'''
            if laser_msg[7] == True:
                #ボタン変更
                self.button_back.place_forget()
                #貼り付け
                self.button_back_lock.place(
                    x = 637,
                    y = 50,
                    anchor=tk.CENTER
                )
            elif laser_msg[7] == False:
                #ボタン変更
                self.button_back_lock.place_forget()
                
                #貼り付け
                self.button_back.place(
                    x = 637,
                    y = 50,
                    anchor=tk.CENTER
                )
            ''''''
            '''cw旋回ボタンの処理'''
            if laser_msg[3] or laser_msg[5]:
                #ボタン変更
                self.button_b_cw.place_forget()
                #貼り付け
                self.button_b_cw_lock.place(
                    x = 1185,
                    y = 382,
                    anchor=tk.CENTER
                )
            elif not laser_msg[3] and not laser_msg[5]:
                #ボタン変更
                self.button_b_cw_lock.place_forget()
                #貼り付け
                self.button_b_cw.place(
                    x = 1185,
                    y = 382,
                    anchor=tk.CENTER
                )
            ''''''
            '''ccw旋回ボタンの処理'''
            if laser_msg[9] or laser_msg[11]:
                #ボタン変更
                self.button_b_ccw.place_forget()
                #貼り付け
                self.button_b_ccw_lock.place(
                    x = 67,
                    y = 382,
                    anchor=tk.CENTER
                )
                
            elif not laser_msg[9] and not laser_msg[11]:
                #ボタン変更
                self.button_b_ccw_lock.place_forget()
                #貼り付け
                self.button_b_ccw.place(
                    x = 67,
                    y = 382,
                    anchor=tk.CENTER
                )
            ''''''
        elif self.flag == 'S_B':   #ユーザが後方停止画面を操作している時
            '''後退ボタンの処理'''
            if laser_msg[7] == True:
                #ボタン変更
                self.button_stop_back.place_forget()
                #貼り付け
                self.button_stop_back_lock.place(
                    x = 637,
                    y = 50,
                    anchor=tk.CENTER
                )
            elif laser_msg[7] == False:
                #ボタン変更
                self.button_stop_back_lock.place_forget()
                
                #貼り付け
                self.button_stop_back.place(
                    x = 637,
                    y = 50,
                    anchor=tk.CENTER
                )
            ''''''
            '''cw旋回ボタンの処理'''
            if laser_msg[3] or laser_msg[5]:
                #ボタン変更
                self.button_stop_b_cw.place_forget()
                #貼り付け
                self.button_stop_b_cw_lock.place(
                    x = 1185,
                    y = 382,
                    anchor=tk.CENTER
                )
            elif not laser_msg[3] and not laser_msg[5]:
                #ボタン変更
                self.button_stop_b_cw_lock.place_forget()
                #貼り付け
                self.button_stop_b_cw.place(
                    x = 1185,
                    y = 382,
                    anchor=tk.CENTER
                )
            ''''''
            '''ccw旋回ボタンの処理'''
            if laser_msg[9] or laser_msg[11]:
                #ボタン変更
                self.button_stop_b_ccw.place_forget()
                #貼り付け
                self.button_stop_b_ccw_lock.place(
                    x = 67,
                    y = 382,
                    anchor=tk.CENTER
                )
                
            elif not laser_msg[9] and not laser_msg[11]:
                #ボタン変更
                self.button_stop_b_ccw_lock.place_forget()
                #貼り付け
                self.button_stop_b_ccw.place(
                    x = 67,
                    y = 382,
                    anchor=tk.CENTER
                )
            ''''''
 
    '''警告シンボルを表示・非表示する関数'''
    def WARNING(self, laser_msg):
        if self.flag == 'F':   #ユーザが前方操作画面を操作している時
            #左前
            if laser_msg[0]:
                self.cvs_forward.itemconfigure(self.img_ID_0, state='normal')
            elif not laser_msg[0]:
                self.cvs_forward.itemconfigure(self.img_ID_0, state='hidden')

            #右前
            if laser_msg[2]:
                self.cvs_forward.itemconfigure(self.img_ID_2, state='normal')
            elif not laser_msg[2]:
                self.cvs_forward.itemconfigure(self.img_ID_2, state='hidden')

            #右
            if laser_msg[4]:
                self.cvs_forward.itemconfigure(self.img_ID_4, state='normal')
            elif not laser_msg[4]:
                self.cvs_forward.itemconfigure(self.img_ID_4, state='hidden')

            #左
            if laser_msg[10]:
                self.cvs_forward.itemconfigure(self.img_ID_10, state='normal')
            elif not laser_msg[10]:
                self.cvs_forward.itemconfigure(self.img_ID_10, state='hidden')

        elif self.flag == 'B':   #ユーザが後方操作画面を操作している時
            #映像から見て左前
            if laser_msg[6]:
                self.cvs_back.itemconfigure(self.img_ID_6_B, state='normal')
            elif not laser_msg[6]:
                self.cvs_back.itemconfigure(self.img_ID_6_B, state='hidden')

            #映像から見て右前
            if laser_msg[8]:
                self.cvs_back.itemconfigure(self.img_ID_8_B, state='normal')
            elif not laser_msg[8]:
                self.cvs_back.itemconfigure(self.img_ID_8_B, state='hidden')

            #映像から見て右
            if laser_msg[10]:
                self.cvs_back.itemconfigure(self.img_ID_10_B, state='normal')
            elif not laser_msg[10]:
                self.cvs_back.itemconfigure(self.img_ID_10_B, state='hidden')

            #映像から見て左
            if laser_msg[4]:
                self.cvs_back.itemconfigure(self.img_ID_4_B, state='normal')
            elif not laser_msg[4]:
                self.cvs_back.itemconfigure(self.img_ID_4_B, state='hidden')
    '''ボタンロック・アンロック用の関数'''
    def lock_button(self):
        global time_start
        #print(arg)
        if not msg_q.empty():   #障害物情報に変化があったとき
            laser_msg = msg_q.get(block=True, timeout=True)
            #print(laser_msg)
            self.delete_and_paste(laser_msg)
            self.WARNING(laser_msg)

            #time_end = time.time()
            #exe_time = time_end - time_start
            #print("処理時間: {:.10f} seconds".format(exe_time))

            self.str = laser_msg   #前回の障害物情報を保持
            msg_q.task_done()

        if self.arg == True:   #画面遷移が行われたとき
            self.delete_and_paste(self.str)
            self.arg = False
        self.after(10, self.lock_button)

    '''衝突防止動作によって停止画面に遷移させるかを判断する関数'''
    def determine_transition(self):
        global state_flag
        #print("関数内："+str(state_flag))
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

            
'''周辺障害物の情報を受け取る関数'''
def receive_laser_data():
    while True:
        try:
            server_address = ('192.168.1.102', 50000)
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(server_address)
            received_data = client_socket.recv(1024)  # データの受信
            array = pickle.loads(received_data)
            #print("障害物情報：", array)
            msg_q.put(array)
            #str_q.put(array)
            msg_q.join()
        except EOFError:
            continue

'''ロボットの状態を受け取る関数'''
def receive_state_data():
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






if __name__ == "__main__":

    root = MyApp()
    
    thread2 = threading.Thread(target=receive_laser_data)
    thread2.start()
    thread3 = threading.Thread(target=receive_state_data)
    thread3.start()
    root.disp_image()
    root.lock_button()
    root.determine_transition()
    

    root.mainloop()


    