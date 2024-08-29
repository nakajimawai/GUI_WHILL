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

mode_flag = 'user' # ユーザ操縦モードか介助者操縦モードかを判断するための変数（user：ユーザ操縦モード、helper：介助者操縦モード）

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

        # 前方、後方カメラをオープンする
        self.capture_F = cv2.VideoCapture(1)
        self.capture_B = cv2.VideoCapture(2)   

        '''シンボル画像用意'''
        #コンフィグレーションファイルからシンボル拡大率（W、H）、透明度（ALPHA）を読込
        self.config = self.read_config('config.txt')
        W = float(self.config['W'])
        H = float(self.config['H'])
        self.alpha = int(self.config.get('ALPHA', 128))

        #走行開始シンボル
        self.img_start = Image.open('start.png')
        self.img_start = self.img_start.resize((int(200 * W), int(200 * H)))
        self.img_start = self.img_start.convert("RGBA")
        self.img_start = self.apply_transparency(self.img_start, self.alpha)
        self.img_start_tk = ImageTk.PhotoImage(self.img_start)
        # 終了シンボル
        self.img_finish = Image.open('finish_letter.png')
        self.img_finish = self.img_finish.resize((150, 100))
        self.img_finish = self.img_finish.convert("RGBA")
        self.img_finish = self.apply_transparency(self.img_finish, self.alpha)
        self.img_finish_tk = ImageTk.PhotoImage(self.img_finish)
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
        #前進シンボル
        self.img_forward = Image.open('forward_3d.png')
        self.img_forward = self.img_forward.resize((int(200 * W), int(200 * H)))
        self.img_forward = self.img_forward.convert("RGBA")
        self.img_forward = self.apply_transparency(self.img_forward, self.alpha)
        self.img_forward_tk = ImageTk.PhotoImage(self.img_forward)
        #停止シンボル
        self.img_stop = Image.open('stop_3d.png')
        self.img_stop = self.img_stop.resize((int(200 * W), int(200 * H)))
        self.img_stop = self.img_stop.convert("RGBA")
        self.img_stop = self.apply_transparency(self.img_stop, self.alpha)
        self.img_stop_tk = ImageTk.PhotoImage(self.img_stop)
        #前進ロックシンボル
        self.img_lock_forward = Image.open('forward_3d_lock.png')
        self.img_lock_forward = self.img_lock_forward.resize((int(200 * W), int(200 * H)))
        self.img_lock_forward = self.img_lock_forward.convert("RGBA")
        self.img_lock_forward = self.apply_transparency(self.img_lock_forward, self.alpha)
        self.img_lock_forward_tk = ImageTk.PhotoImage(self.img_lock_forward)
        ''''''

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
        #-----------------------------helper_menu_frame------------------------------
        #前方画面フレーム作成
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
            337,
            383,
            image = self.img_lock_forward_tk,
            anchor = tk.CENTER,
            tag = "lock_S_F_forward"
        )
        
        ''''''
        '''ロボット操縦シンボル'''
        # 前進シンボル
        self.id_S_F_forward = self.cvs_stop_forward.create_image(
            337,
            383,
            image = self.img_forward_tk,
            anchor = tk.CENTER,
            tag = "S_F_forward"
        )
        self.cvs_stop_forward.tag_bind(
            self.id_S_F_forward,
            '<Button-1>',
            lambda e: [self.changePage(self.forward_frame), self.change_frame_flag("F"), self.forward()]
            #lambda e: [self.change_frame_flag("F"), self.forward(), self.start_blinking(self.id_forward), self.changePage(self.forward_frame)]
            )

        ''''''        
        '''ロボット操作以外のシンボル'''
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

        ###シンボル設置###
        '''ロボット操縦シンボル'''
        # 停止シンボル
        self.id_F_stop = self.cvs_forward.create_image(
            957,
            383,
            image = self.img_stop_tk,
            anchor = tk.CENTER,
            tag = "stop"
        )
        self.cvs_forward.tag_bind(
            self.id_F_stop,
            '<Button-1>',
            lambda e: [self.change_frame_flag("S_F"), self.stop(), self.changePage(self.stop_forward_frame)]
            )

        #--------------------------------------------------------------------------------------------------------

        #メニュー画面を最前面で表示
        self.menu_frame.tkraise()

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

    '''1フレーム分のデータを受け取って表示する関数'''
    def disp_image(self):
        '''canvasに画像を表示'''

        #前方カメラか後方カメラどちらかの映像をフラグの状態によって取得
        if self.flag == "F" or self.flag == "S_F" or self.flag == "M_F" or self.flag == "H_F":
            ret, data = self.capture_F.read()
    
        elif self.flag == "B" or self.flag == "S_B" or self.flag == "M_B":
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
            ID_B = self.cvs_back.create_image(0,0,anchor='nw',image=self.bg)
            self.cvs_back.tag_lower(ID_B)

        elif self.flag == 'S_B':
            self.cvs_stop_back.create_image(0,0,anchor='nw',image=self.bg)

        elif self.flag == 'M_F':
            self.cvs_menu.create_image(0,0,anchor='nw',image=self.bg, tag = "background")
            self.cvs_menu.tag_lower('background')

        elif self.flag == 'M_B':
            self.cvs_menu_back.create_image(0,0,anchor='nw',image=self.bg)

        elif self.flag == 'H_F': # 介助者操縦モードのメニュー画面
            self.cvs_menu_helper_F.create_image(0,0,anchor='nw',image=self.bg, tag = "background")
            self.cvs_menu_helper_F.tag_lower('background')          
            
            #画像更新のために10msスレッドを空ける
        self.after(10, self.disp_image)


    '''文字列送信用'''
    def control(self, data):
        HOST='192.168.1.102'
        PORT=12345
        BUFFER=4096
            # Define socket communication type ipv4, tcp
        self.soc=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            #connect to the server 
        self.soc.connect((HOST,PORT))
        if data == "exit":
            pass
        else:
            try:
                self.soc.send(data.encode("utf-8"))
            except ConnectionResetError:
                pass
        buf=self.soc.recv(BUFFER)

    '''シンボルごとの文字列を文字列送信用の関数controlに送る関数たち'''
    def forward(self):
        print("前進")
        self.control("w")

    def stop(self):
        print("停止")
        self.control("s")

    def helper(self):
        print("介助者操縦モード")
        global mode_flag
        mode_flag = "helper"
        self.control("helper")

    def user(self):
        print("ユーザ操縦モード")
        global mode_flag
        mode_flag = "user"
        self.control("user")

    def menu(self):
        global mode_flag
        if mode_flag == "user":
            print("ユーザ操縦モードのメニュー画面へ")
            self.changePage(self.menu_frame)
            self.change_frame_flag("M_F")
        elif mode_flag == "helper":
            print("介助者操縦モードのメニュー画面へ")
            self.changePage(self.menu_helper_F_frame)
            self.change_frame_flag("H_F")
    
    '''後方走行時 → メニュー画面 → 走行開始 を選んだ場合も後方カメラ映像を映すための関数'''
    def start_running(self):
        print("走行開始")
        self.control("run")
        if self.flag == "M_F" or self.flag == "H_F":
            self.arg = True
            self.stop_forward_frame.tkraise()
            self.change_frame_flag("S_F")
        elif self.flag == "M_B":
            self.arg = True
            self.stop_back_frame.tkraise()
            self.change_frame_flag("S_B")


    '''フレームごとで映像を表示し続けるために、フラグを変更する関数'''
    def change_frame_flag(self, frame_flag):
        self.flag = frame_flag

    '''画面遷移用の関数'''
    def changePage(self, page):
        self.arg = True
        page.tkraise()   #指定のフレームを最前面に移動

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

    '''シンボルを貼り変える関数'''
    def delete_and_paste(self, laser_msg):

        if self.flag == 'S_F':   #ユーザが前方停止画面を操作している時
            # 前進シンボルの処理
            
            if laser_msg[1] == True:
                self.cvs_stop_forward.itemconfigure(self.id_S_F_forward, state = 'hidden') # 前進シンボルを非表示
                self.cvs_stop_forward.itemconfigure(self.id_lock_S_F_forward, state = 'normal') # 前進ロックシンボルを表示
            else:
                self.cvs_stop_forward.itemconfigure(self.id_S_F_forward, state = 'normal') # 前進シンボルを表示
                self.cvs_stop_forward.itemconfigure(self.id_lock_S_F_forward, state = 'hidden') # 前進ロックシンボルを非表示


    '''シンボルロック・アンロック関数'''
    def lock_symbol(self):
        if not msg_q.empty():   #障害物情報に変化があったとき
            laser_msg = msg_q.get(block=True, timeout=True)
            self.delete_and_paste(laser_msg)

            self.str = laser_msg   #遷移後の画面でもシンボルロックするために前回の障害物情報を保持
            msg_q.task_done()

        if self.arg == True:   #画面遷移が行われたとき
            self.delete_and_paste(self.str)
            self.arg = False

        self.after(10, self.lock_symbol)

    '''衝突防止動作によって停止画面に遷移させるかを判断する関数'''
    def determine_transition(self):
        global state_flag
        if not state_q.empty():
            state_msg = state_q.get(block=True, timeout=True)
            if not state_msg:
                if self.flag == "F":
                    self.changePage(self.stop_forward_frame)
                    self.change_frame_flag("S_F")
            state_q.task_done()
        
        self.after(10, self.determine_transition)

'''周辺障害物の情報を受け取る関数'''
def receive_laser_data():
    global client_socket
    global mode_flag
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

if __name__ == "__main__":
    root = MyApp()

    thread2 = threading.Thread(target=receive_laser_data)
    thread2.start()
    thread3 = threading.Thread(target=receive_state_data)
    thread3.start()

    root.disp_image()
    root.lock_symbol()
    root.determine_transition()

    root.mainloop()
