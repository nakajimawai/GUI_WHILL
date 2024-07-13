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

img_flag = 'M_F'   #前方カメラか後方カメラ、どちらを受け取る画像データにするか判断するための変数（F：前方、B：後方、M：Menu、S：停止中）

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
        #終了シンボル
        self.img_finish = Image.open('finish_letter.png')
        self.img_finish = self.img_finish.resize((150, 100))
        #メニューへの画面遷移シンボル
        self.img_menu = Image.open('menu.png')
        self.img_menu = self.img_menu.resize((200, 100))
        #前進シンボル
        self.img_forward = Image.open('forward_3d.png')
        self.img_forward = self.img_forward.resize((int(200 * W), int(200 * H)))
        #停止シンボル
        self.img_stop = Image.open('stop_3d.png')
        self.img_stop = self.img_stop.resize((int(200 * W), int(200 * H)))
        #前進ロックシンボル
        self.img_forward_lock = Image.open('forward_3d_lock.png')
        self.img_forward_lock = self.img_forward_lock.resize((int(200 * W), int(200 * H)))
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
        
        #走行開始シンボル
        self.img_start, id_start = self.make_transparent_button(self.img_start, self.cvs_menu, 637, 350, self.alpha)
        self.cvs_menu.tag_bind(id_start, '<Button-1>', lambda e: self.start_running())
        
        #終了シンボル
        self.img_finish, id_finish = self.make_transparent_button(self.img_finish, self.cvs_menu, 1195, 720, self.alpha)
        self.cvs_menu.tag_bind(id_finish, '<Button-1>', lambda e: self.Finish())

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
        #停止シンボル
        self.img_stop, id_stop = self.make_transparent_button(self.img_stop, self.cvs_forward, 957, 383, self.alpha)
        self.cvs_forward.tag_bind(
            id_stop,
            '<Button-1>',
            lambda e: [self.changePage(self.stop_forward_frame), self.change_frame_flag("S_F"), self.stop()]
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

        '''ロボット操作シンボル'''
        #停止画面の前進シンボル
        #self.img_forward, id_forward = self.make_transparent_button(self.img_forward, self.cvs_stop_forward, 337, 383, self.alpha)

        # ロック・アンロックが繰り返し行えるように個別でタグ付け
        self.img_forward = self.img_forward.convert("RGBA")
        self.img_forward.putalpha(self.alpha)
        self.img_forward_tk = ImageTk.PhotoImage(self.img_forward)
        id_S_F_forward = self.cvs_stop_forward.create_image(
            337,
            383,
            image = self.img_forward_tk,
            anchor = tk.CENTER,
            tag = "S_F_forward"
        )
        self.cvs_stop_forward.tag_bind(
            id_S_F_forward,
            '<Button-1>',
            lambda e: [self.changePage(self.forward_frame), self.change_frame_flag("F"), self.forward()]
            )

        ''''''
        '''ロックシンボル'''
        #停止画面の前進ロックシンボル
        
        # ロック・アンロックが繰り返し行えるように個別でタグ付け
        self.img_forward_lock = self.img_forward_lock.convert("RGBA")
        self.img_forward_lock.putalpha(self.alpha)
        self.img_forward_lock_tk = ImageTk.PhotoImage(self.img_forward_lock)
        self.cvs_stop_forward.create_image(
            337,
            383,
            image = self.img_forward_lock_tk,
            anchor = tk.CENTER,
            tag = "S_F_forward_lock"
        )
        
        ''''''
        '''ロボット操作以外のシンボル'''
        #メニューへのシンボル
        self.img_menu, id_menu = self.make_transparent_button(self.img_menu, self.cvs_stop_forward, 110, 682, self.alpha)
        self.cvs_stop_forward.tag_bind(
            id_menu,
            '<Button-1>',
            lambda e: [self.changePage(self.menu_frame), self.change_frame_flag("M_F")]
            )
        ''''''
        #--------------------------------------------------------------------------------------------------------

        #メニュー画面を最前面で表示
        self.menu_frame.tkraise()

    '''シンボルを透明にする関数'''
    def make_transparent_button(self, img, canvas, x, y, ALPHA):
        img = img.convert("RGBA")
        img.putalpha(ALPHA)
        img = ImageTk.PhotoImage(img)
        id = canvas.create_image(
            x,
            y,
            image = img,
            anchor = tk.CENTER
        )
        return img ,id

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

    '''ボタンごとの文字列を文字列送信用の関数controlに送る関数たち'''
    #ボタンforward
    def forward(self):
        print("前進")
        #self.control("w")
    #ボタンstop
    def stop(self):
        print("停止")
        #self.control("s")
    
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
        print("終了")
        #self.control("q")
        #self.soc.close()
        self.destroy()#destroy()クラスメソッドでtkinterウィンドウを閉じる
        sys.exit()

    '''シンボルを貼り変える関数'''
    def delete_and_paste(self, laser_msg):

        if self.flag == 'S_F':   #ユーザが前方停止画面を操作している時
            '''前進シンボルの処理'''
            if laser_msg[1] == True:
                #前進シンボル削除
                self.cvs_stop_forward.delete("S_F_forward")
                self.cvs_stop_forward.delete("S_F_forward_lock")
                #前進ロックシンボル貼り付け
                self.cvs_stop_forward.create_image(
                337,
                383,
                image = self.img_forward_lock_tk,
                anchor = tk.CENTER,
                tag = "S_F_forward_lock"
                )                
                
            elif laser_msg[1] == False:
                #前進ロックシンボル削除
                self.cvs_stop_forward.delete("S_F_forward")
                self.cvs_stop_forward.delete("S_F_forward_lock")
                #前進シンボル貼り付け
                id_S_F_forward = self.cvs_stop_forward.create_image(
                337,
                383,
                image = self.img_forward_tk,
                anchor = tk.CENTER,
                tag = "S_F_forward"
                )
                #前進シンボルに関数をバインド
                self.cvs_stop_forward.tag_bind(id_S_F_forward, '<Button-1>', lambda e: [self.changePage(self.forward_frame), self.change_frame_flag("F"), self.forward()]) 
            ''''''


    '''ボタンロック・アンロック関数'''
    def lock_button(self):
        if not msg_q.empty():   #障害物情報に変化があったとき
            laser_msg = msg_q.get(block=True, timeout=True)
            self.delete_and_paste(laser_msg)

            self.str = laser_msg   #遷移後の画面でもシンボルロックするために前回の障害物情報を保持
            msg_q.task_done()

        if self.arg == True:   #画面遷移が行われたとき
            self.delete_and_paste(self.str)
            self.arg = False

        self.after(10, self.lock_button)

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
    #root.determine_transition()

    root.mainloop()
