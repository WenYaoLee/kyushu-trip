"""ZPL Designer: local Tkinter prototype (Python 3.9+)."""
import json
import configparser
import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

try:
    import qrcode as _qrcode
except ImportError:
    _qrcode = None  # Without qrcode, show an orientation-aware schematic.

DPI_OPTIONS = (300,)

class Designer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Python ZPL Designer 2.0 - QR 大小與旋轉預覽')
        self.geometry('1100x720')
        self.items = []
        self.selected = None
        self.selected_indices = set()
        self._syncing_object_list = False
        self.drag = None
        self.resize_handles = {}
        self.dpi = tk.IntVar(value=300)
        self.width_mm = tk.StringVar(value='100')
        self.height_mm = tk.StringVar(value='100')
        self.width_dots = tk.StringVar(value='1181')
        self.height_dots = tk.StringVar(value='1181')
        self.dimension_unit = tk.StringVar(value='mm')
        self.dimension_source = 'mm'
        self.dimension_exact = True
        self._last_applied = None
        self.props = {k: tk.StringVar() for k in ('text','x','y','w','h','rotation','qr_mag','qr_model','xg_x','xg_y')}
        self.zoom = 0.7
        self._qr_cache = {}
        self.align_ref = tk.StringVar(value="")
        self.align_reference_indices = []
        self.unknown = []
        self.next_item_number = 1
        self.field_delimiter = tk.StringVar(value=",")
        self.record_delimiter = tk.StringVar(value="")
        self.ini_program = tk.StringVar(value="TA-TAN CARD PROGRAM")
        self.ini_setup = {"Printer Model":"zebra","OUTPORT":"lpt1","BAUD RATE":"57600","STOP BITS":"1","DATA BIT":"8","Parity":"n","Output file Path":"","LOGO   file Path":"","PagePreambleFile":"","PagePostambleFile":"","Form Show":"No"}
        self.ini_extra = {}
        self.label_home = (0, 0)
        self.pq_placeholder = None
        self._ui()
        self.new_label()

    def _ui(self):
        toolbar = ttk.Frame(self, padding=7)
        toolbar.pack(fill='x')
        for label, command in [('新建',self.new_label),('開啟 TXT/FMT',self.open_zpl),('開啟 INI',self.open_ini),('開啟專案',self.open_project),('儲存專案',self.save_project),('匯出 FMT + TXT + JSON + INI',self.export_zpl)]:
            ttk.Button(toolbar,text=label,command=command).pack(side='left',padx=2)
        ttk.Separator(self).pack(fill='x')
        settings = ttk.Frame(self,padding=7)
        settings.pack(fill='x')
        ttk.Label(settings,text='編輯單位').pack(side='left')
        ttk.Combobox(settings,textvariable=self.dimension_unit,values=('mm','dots'),width=6,state='readonly').pack(side='left',padx=4)
        ttk.Label(settings,text='寬').pack(side='left')
        self.dimension_width = ttk.Entry(settings,width=9)
        self.dimension_width.pack(side='left',padx=3)
        ttk.Label(settings,text='高').pack(side='left')
        self.dimension_height = ttk.Entry(settings,width=9)
        self.dimension_height.pack(side='left',padx=3)
        ttk.Label(settings,text='DPI').pack(side='left')
        self.dpi_box=ttk.Combobox(settings,textvariable=self.dpi,values=DPI_OPTIONS,width=5,state='readonly')
        self.dpi_box.pack(side='left',padx=4)
        ttk.Button(settings,text='套用尺寸',command=self.apply_dimensions).pack(side='left',padx=4)
        self.dimension_note=ttk.Label(settings,text='')
        self.dimension_note.pack(side='left',padx=6)
        self.dimension_unit.trace_add('write',lambda *_:self._bind_dimension_entries())
        self.dpi_box.bind('<<ComboboxSelected>>',lambda e:self._dpi_changed())
        self._bind_dimension_entries()
        body=ttk.Frame(self)
        body.pack(fill='both',expand=True)
        left_host=ttk.Frame(body,width=280)
        left_host.pack(side='left',fill='y')
        left_host.pack_propagate(False)
        left_canvas=tk.Canvas(left_host,highlightthickness=0,width=260)
        left_scroll=ttk.Scrollbar(left_host,orient='vertical',command=left_canvas.yview)
        left_scroll.pack(side='right',fill='y')
        left_canvas.pack(side='left',fill='both',expand=True)
        left_canvas.configure(yscrollcommand=left_scroll.set)
        left=ttk.Frame(left_canvas,padding=8)
        left_window=left_canvas.create_window((0,0),window=left,anchor='nw')
        left.bind('<Configure>',lambda e:left_canvas.configure(scrollregion=left_canvas.bbox('all')))
        left_canvas.bind('<Configure>',lambda e:left_canvas.itemconfigure(left_window,width=e.width))
        def wheel(e):
            if e.delta:left_canvas.yview_scroll(-int(e.delta/120),'units')
            return 'break'
        def enter(e):left_canvas.bind_all('<MouseWheel>',wheel)
        def leave(e):left_canvas.unbind_all('<MouseWheel>')
        left_canvas.bind('<Enter>',enter);left_canvas.bind('<Leave>',leave)
        left.bind('<Enter>',enter);left.bind('<Leave>',leave)
        ttk.Label(left,text='新增物件',font=('Arial',11,'bold')).pack(anchor='w')
        for kind,label in [('text','XG 文字'),('native_text','原生文字'),('barcode','Code128 條碼'),('qr','QR Code'),('box','方框'),('hline','橫線'),('vline','直線')]:
            ttk.Button(left,text=label,command=lambda k=kind:self.add(k)).pack(fill='x',pady=3)
        ttk.Button(left,text='刪除選取物件',command=self.delete_selected).pack(fill='x',pady=10)
        ttk.Label(left,text='物件清單',font=('Arial',11,'bold')).pack(anchor='w',pady=(10,5))
        list_frame=ttk.Frame(left)
        list_frame.pack(fill='x')
        self.object_list=ttk.Treeview(list_frame,columns=('type','content'),show='headings',height=8,selectmode='extended')
        self.object_list.heading('type',text='類型');self.object_list.heading('content',text='內容')
        self.object_list.column('type',width=75,stretch=False);self.object_list.column('content',width=125)
        self.object_list.pack(side='left',fill='x',expand=True)
        scroll=ttk.Scrollbar(list_frame,orient='vertical',command=self.object_list.yview)
        scroll.pack(side='right',fill='y');self.object_list.configure(yscrollcommand=scroll.set)
        self.object_list.bind('<<TreeviewSelect>>',self.on_list_select)
        ttk.Label(left,text='屬性',font=('Arial',11,'bold')).pack(anchor='w',pady=(10,5))
        for key,label in [('text','內容'),('x','X'),('y','Y'),('w','寬 / 字寬'),('h','高 / 字高')]:
            ttk.Label(left,text=label).pack(anchor='w')
            ttk.Entry(left,textvariable=self.props[key],width=23).pack(pady=2)
        ttk.Label(left,text='旋轉角度（XG 文字寫入 INI ROTATE）').pack(anchor='w')
        ttk.Combobox(left,textvariable=self.props['rotation'],values=('0','90','180','270'),width=20,state='readonly').pack(pady=2)
        ttk.Label(left,text='QR 倍率 / 型號（QR 使用；預覽依倍率即時縮放）').pack(anchor='w')
        qrrow=ttk.Frame(left);qrrow.pack(fill='x')
        ttk.Entry(qrrow,textvariable=self.props['qr_mag'],width=9).pack(side='left',padx=2)
        ttk.Entry(qrrow,textvariable=self.props['qr_model'],width=9).pack(side='left',padx=2)
        ttk.Label(left,text='XG 水平 / 垂直倍率（文字使用）').pack(anchor='w')
        xgrow=ttk.Frame(left);xgrow.pack(fill='x')
        ttk.Entry(xgrow,textvariable=self.props['xg_x'],width=9).pack(side='left',padx=2)
        ttk.Entry(xgrow,textvariable=self.props['xg_y'],width=9).pack(side='left',padx=2)
        ttk.Button(left,text='套用屬性',command=self.apply_props).pack(fill='x',pady=8)
        ttk.Label(left,text='INI 設定',font=('Arial',11,'bold')).pack(anchor='w',pady=(8,3))
        ttk.Label(left,text='Field Delimiter（欄位分隔符）').pack(anchor='w')
        ttk.Combobox(left,textvariable=self.field_delimiter,values=(',', ';', ':'),width=20).pack(fill='x',pady=2)
        ttk.Label(left,text='Record Delimiter（記錄分隔符）').pack(anchor='w')
        ttk.Entry(left,textvariable=self.record_delimiter,width=23).pack(fill='x',pady=2)
        ttk.Label(left,text='PROGRAM NAME').pack(anchor='w')
        ttk.Entry(left,textvariable=self.ini_program,width=23).pack(fill='x',pady=2)
        ttk.Label(left,text='ITEM INI 屬性（單選時可修改）',font=('Arial',10,'bold')).pack(anchor='w',pady=(8,2))
        self.ini_props={k:tk.StringVar() for k in ('DATA LENGTH','PROMPT','FONT NAME','FONT SIZE','ROTATE')}
        for key,var in self.ini_props.items():
            ttk.Label(left,text=key).pack(anchor='w')
            ttk.Entry(left,textvariable=var,width=23).pack(fill='x',pady=1)
        ttk.Button(left,text='套用 ITEM INI 屬性',command=self.apply_ini_props).pack(fill='x',pady=5)
        ttk.Label(left,text='XG 字型依 INI 預覽；QR 大小依倍率與內容估算\nQR 旋轉會同步更新預覽；實際列印請測試',foreground='#555').pack(anchor='w',pady=3)
        ttk.Label(left,text='精準對齊（單位：dots）',font=('Arial',11,'bold')).pack(anchor='w',pady=(8,3))
        ttk.Label(left,text='多選：框選畫布或 Ctrl+點選；基準為第一個選取物件').pack(anchor='w',pady=2)
        ttk.Label(left,text='單選對齊基準物件').pack(anchor='w')
        self.align_ref_box=ttk.Combobox(left,textvariable=self.align_ref,width=24,state='readonly')
        self.align_ref_box.pack(fill='x',pady=2)
        align_grid=ttk.Frame(left);align_grid.pack(fill='x',pady=3)
        alignment_actions=[('靠左','left'),('水平置中','center_x'),('靠右','right'),
                           ('靠上','top'),('垂直置中','center_y'),('靠下','bottom')]
        for j,(label,mode) in enumerate(alignment_actions):
            ttk.Button(align_grid,text=label,width=10,command=lambda m=mode:self.align_selected(m)).grid(
                row=j//3,column=j%3,padx=1,pady=2,sticky='ew')
        for j in range(3):align_grid.columnconfigure(j,weight=1)
        ttk.Label(left,text='微調：方向鍵 ±1 dot；Shift+方向鍵 ±10 dots',foreground='#555').pack(anchor='w',pady=2)
        self.bind_all('<KeyPress>',self.nudge_key,add='+')

        ttk.Label(left,text='拖拉物件可移動；拖拉藍色控制點可調整\n方框、橫線、直線大小\n條碼及 QR 預覽僅為示意\n實際輸出請以印表機測試',foreground='#555').pack(anchor='w',pady=12)
        center=ttk.Frame(body)
        center.pack(side='left',fill='both',expand=True)
        self.canvas=tk.Canvas(center,bg='#d9dee3',highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Button-1>',self.on_down)
        self.canvas.bind('<Control-Button-1>',self.on_ctrl_down)
        self.canvas.bind('<B1-Motion>',self.on_move)
        self.canvas.bind('<ButtonRelease-1>',self.on_up)
        self.canvas.bind('<Configure>',lambda e:self.render())
        self.status=tk.StringVar(value='就緒')
        ttk.Label(self,textvariable=self.status,anchor='w',padding=6).pack(fill='x')

    @staticmethod
    def mm_to_dots(value, dpi):
        return round(float(value)*int(dpi)/25.4)

    @staticmethod
    def dots_to_mm(value, dpi):
        return float(value)*25.4/int(dpi)

    @staticmethod
    def fmt_mm(value):
        return f'{value:.5f}'.rstrip('0').rstrip('.')

    def _bind_dimension_entries(self):
        if not hasattr(self,'dimension_width'):return
        unit=self.dimension_unit.get()
        self.dimension_width.configure(textvariable=self.width_mm if unit=='mm' else self.width_dots)
        self.dimension_height.configure(textvariable=self.height_mm if unit=='mm' else self.height_dots)
        self._dimension_note()
        self._last_applied=(self.dimension_unit.get(),self.width_mm.get(),self.height_mm.get(),self.width_dots.get(),self.height_dots.get(),int(self.dpi.get()))

    def _dimension_note(self):
        if not hasattr(self,'dimension_note'):return
        self.dimension_note.configure(text=f'{self.width_mm.get()}×{self.height_mm.get()} mm  |  {self.width_dots.get()}×{self.height_dots.get()} dots'+('  (換算)' if not self.dimension_exact else ''))

    def _dpi_changed(self):
        # Changing printer resolution preserves physical size, recalculates dot size.
        try:
            dpi=int(self.dpi.get())
            self.width_dots.set(str(self.mm_to_dots(self.width_mm.get(),dpi)))
            self.height_dots.set(str(self.mm_to_dots(self.height_mm.get(),dpi)))
            self.dimension_source='mm'
            self._dimension_note();self.render()
            self._last_applied=(self.dimension_unit.get(),self.width_mm.get(),self.height_mm.get(),self.width_dots.get(),self.height_dots.get(),int(self.dpi.get()))
        except (ValueError,tk.TclError):pass

    def apply_dimensions(self):
        try:
            current=(self.dimension_unit.get(),self.width_mm.get(),self.height_mm.get(),self.width_dots.get(),self.height_dots.get(),int(self.dpi.get()))
            if current==self._last_applied:return True
            dpi=int(self.dpi.get())
            if dpi not in DPI_OPTIONS:raise ValueError
            if self.dimension_unit.get()=='mm':
                w,h=float(self.width_mm.get()),float(self.height_mm.get())
                if not (0<w<=500 and 0<h<=500):raise ValueError
                self.width_dots.set(str(self.mm_to_dots(w,dpi)))
                self.height_dots.set(str(self.mm_to_dots(h,dpi)))
                self.dimension_source='mm';self.dimension_exact=True
            else:
                w,h=int(self.width_dots.get()),int(self.height_dots.get())
                if not (0<w<=round(500*dpi/25.4) and 0<h<=round(500*dpi/25.4)):raise ValueError
                self.width_mm.set(self.fmt_mm(self.dots_to_mm(w,dpi)))
                self.height_mm.set(self.fmt_mm(self.dots_to_mm(h,dpi)))
                self.dimension_source='dots';self.dimension_exact=False
            self._dimension_note();self.render()
            self._last_applied=(self.dimension_unit.get(),self.width_mm.get(),self.height_mm.get(),self.width_dots.get(),self.height_dots.get(),int(self.dpi.get()))
            return True
        except (ValueError,tk.TclError):
            messagebox.showerror('尺寸錯誤','請輸入有效的正數尺寸（mm 需小於等於 500；dots 必須為整數）')
            return False

    def dimensions(self):
        try:
            w,h=int(self.width_dots.get()),int(self.height_dots.get())
            if w<=0 or h<=0:raise ValueError
            return w,h
        except (ValueError,tk.TclError):
            return None

    def new_label(self):
        # A new label always starts at 100 × 100 mm / 300 DPI.
        self.dpi.set(300)
        self.width_mm.set('100')
        self.height_mm.set('100')
        self.width_dots.set(str(self.mm_to_dots(100, 300)))
        self.height_dots.set(str(self.mm_to_dots(100, 300)))
        self.dimension_unit.set('mm')
        self.dimension_source='mm'
        self.dimension_exact=True
        self.items=[];self.selected=None;self.selected_indices=set();self.unknown=[];self.next_item_number=1;self.label_home=(0,0);self.pq_placeholder=None
        self._bind_dimension_entries()
        self._dimension_note();self.render()

    def add(self,kind):
        name = f'ITEM{self._next_number():04d}' if kind in ('text','barcode','qr') else ''
        if name: self.next_item_number += 1
        obj={'kind':kind,'text':name if kind in ('text','barcode','qr') else '', 'x':40,'y':40+len(self.items)*45,'w':170,'h':45,'rotation':0}
        if kind=='text':obj.update(w=170,h=45,xg_x=1,xg_y=1)
        if kind=='native_text':obj.update(text='MSL:',w=44,h=44)
        if kind=='barcode':obj.update(w=170,h=40,by_width=2,by_ratio=3,by_height=40,bc_orientation='',bc_print='Y',bc_above='N',bc_check='N')
        if kind=='qr':obj.update(w=100,h=100,qr_model=2,qr_mag=7,qr_prefix='M,')
        if kind=='hline':obj.update(w=170,h=2)
        if kind=='vline':obj.update(w=2,h=170)
        self.items.append(obj);self.next_item_number=self._next_number();self._ensure_ini(obj);self.select(len(self.items)-1);self.render()

    def refresh_list(self):
        """Refresh the Treeview without recursively handling its own selection events.

        Tk queues <<TreeviewSelect>> events. Rebuilding the list on every render
        used to create an infinite render -> select event -> render cycle.
        """
        if not hasattr(self, 'object_list'):
            return
        names = {'text':'XG 文字','native_text':'原生文字','barcode':'Code128',
                 'qr':'QR','box':'方框','hline':'橫線','vline':'直線'}
        tree = self.object_list
        self._syncing_object_list = True
        try:
            desired = [str(i) for i in range(len(self.items))]
            existing = list(tree.get_children())
            if existing != desired:
                tree.delete(*existing)
                for i, obj in enumerate(self.items):
                    tree.insert('', 'end', iid=str(i), values=(
                        names.get(obj['kind'],obj['kind']),str(obj.get('text',''))[:22]))
            else:
                for i, obj in enumerate(self.items):
                    values=(names.get(obj['kind'],obj['kind']),str(obj.get('text',''))[:22])
                    if tuple(tree.item(str(i),'values')) != values:
                        tree.item(str(i),values=values)
            wanted={str(i) for i in self.selected_indices if 0 <= i < len(self.items)}
            current=set(tree.selection())
            if current != wanted:
                tree.selection_set(tuple(sorted(wanted,key=int)))
        finally:
            self._syncing_object_list = False

    def on_list_select(self,event):
        if self._syncing_object_list:
            return
        ids=self.object_list.selection()
        indices={int(i) for i in ids if i.isdigit() and int(i)<len(self.items)}
        if indices == self.selected_indices:
            return
        if indices:
            self.select(min(indices),indices)
        else:
            self.select(None)
        self.render()

    def select(self,index,indices=None):
        self.selected=index
        self.selected_indices=set(indices if indices is not None else ([index] if index is not None else []))
        if index is None:
            for v in self.props.values():v.set('')
        else:
            for k,v in self.props.items():v.set(str(self.items[index].get(k,0 if k=='rotation' else '')))
            if self.items[index]['kind']=='text':
                self._ensure_ini(self.items[index])
                self.props['rotation'].set(str(self._xg_rotation(self.items[index])))
        self._load_ini_props()

    def _refresh_alignment_references(self):
        """Keep the combobox mapped to object indices without relying on ITEM uniqueness."""
        refs=[];labels=[]
        for i,obj in enumerate(self.items):
            if i==self.selected:continue
            refs.append(i)
            labels.append(f'{i+1:02d}  {obj.get("kind", "")}  {str(obj.get("text", ""))[:14]}')
        self.align_reference_indices=refs
        self.align_ref_box.configure(values=labels)
        if self.align_ref.get() not in labels:
            self.align_ref.set(labels[0] if labels else '')

    def align_selected(self,mode):
        """Multi-selection: first selected index is the anchor; single selection: combobox anchor."""
        selected=sorted(self.selected_indices)
        if not selected:return
        if len(selected)>1:
            reference=self.items[selected[0]]
            targets=[self.items[i] for i in selected[1:]]
        else:
            pos=self.align_ref_box.current()
            if pos<0 or pos>=len(self.align_reference_indices):return
            reference=self.items[self.align_reference_indices[pos]]
            targets=[self.items[selected[0]]]
        rx,ry,rw,rh=(int(reference[k]) for k in ('x','y','w','h'))
        for target in targets:
            tw,th=int(target['w']),int(target['h'])
            if mode=='left':target['x']=rx
            elif mode=='center_x':target['x']=rx+(rw-tw)//2
            elif mode=='right':target['x']=rx+rw-tw
            elif mode=='top':target['y']=ry
            elif mode=='center_y':target['y']=ry+(rh-th)//2
            elif mode=='bottom':target['y']=ry+rh-th
        self.render()

    def nudge_key(self,event):
        """Keyboard nudging, but never intercept typing in editable controls."""
        if not self.selected_indices or event.keysym not in ('Left','Right','Up','Down'):
            return
        widget=event.widget
        if isinstance(widget,(tk.Entry,tk.Text,ttk.Entry,ttk.Combobox,ttk.Treeview)):
            return
        delta=10 if (event.state & 0x0001) else 1
        dx={'Left':-delta,'Right':delta}.get(event.keysym,0)
        dy={'Up':-delta,'Down':delta}.get(event.keysym,0)
        for i in self.selected_indices:
            obj=self.items[i]
            obj['x']=int(obj['x'])+dx
            obj['y']=int(obj['y'])+dy
        self.render()
        return 'break'

    def delete_selected(self):
        if self.selected_indices:
            for i in sorted(self.selected_indices,reverse=True):self.items.pop(i)
            self._renumber_items()
            self.select(None);self.render()

    def apply_props(self):
        if self.selected is None:return
        try:
            obj=self.items[self.selected]
            values={k:int(self.props[k].get()) for k in ('x','y','w','h')}
            if min(values['w'],values['h'])<=0:raise ValueError
            rotation=int(self.props['rotation'].get())
            if rotation not in (0,90,180,270):raise ValueError
            obj.update(values);obj['rotation']=rotation;obj['text']=self.props['text'].get()
            if obj['kind']=='text':
                self._ensure_ini(obj)
                obj['ini']['ROTATE']=str(rotation) if rotation else ''
            self._renumber_items()
            if obj['kind']=='qr':
                mag=int(self.props['qr_mag'].get() or obj.get('qr_mag',7))
                model=int(self.props['qr_model'].get() or obj.get('qr_model',2))
                if not (1<=mag<=10 and model in (1,2)):raise ValueError
                obj.update(qr_mag=mag,qr_model=model)
            if obj['kind']=='text':
                xx=int(self.props['xg_x'].get() or obj.get('xg_x',1))
                yy=int(self.props['xg_y'].get() or obj.get('xg_y',1))
                if not (1<=xx<=10 and 1<=yy<=10):raise ValueError
                obj.update(xg_x=xx,xg_y=yy)
            self.render()
        except ValueError:
            messagebox.showerror('輸入錯誤','請確認座標、尺寸、QR 倍率及 XG 倍率為有效整數')

    def _preview_font(self, obj):
        """Convert printer dots to Tk canvas pixels; negative Tk sizes are pixel sizes."""
        if obj['kind'] == 'text':
            ini = obj.get('ini') or {}
            raw = ini.get('FONT SIZE', '54')
            try:
                dots = float(raw)
                if dots <= 0: raise ValueError
            except (ValueError, TypeError):
                dots = 54.0
            name = str(ini.get('FONT NAME', 'arial bold')).strip() or 'Arial'
        else:
            dots = float(obj.get('h', 44))
            name = 'Arial'
        lower = name.lower()
        weight = 'bold' if 'bold' in lower else 'normal'
        slant = 'italic' if 'italic' in lower else 'roman'
        family = re.sub(r'\b(bold|italic|regular)\b', '', name, flags=re.I).strip() or 'Arial'
        # Tk uses negative sizes for exact screen pixels, not points.
        pixels = max(1, round(dots * self.zoom))
        return tkfont.Font(family=family, size=-pixels, weight=weight, slant=slant)

    def _qr_matrix(self, obj):
        """Return a QR preview matrix (without quiet zone) and rotate it clockwise.

        When the optional qrcode package is available, the matrix is generated
        from the field data. Otherwise a clearly schematic finder-pattern
        preview is used; the ZPL output is independent of this dependency.
        """
        content = str(obj.get('text', ''))
        model = int(obj.get('qr_model', 2))
        prefix = str(obj.get('qr_prefix', 'M,'))
        rotation = int(obj.get('rotation', 0)) % 360
        key = (content, model, prefix, rotation)
        if key in self._qr_cache:
            return self._qr_cache[key]
        if _qrcode is not None:
            level = prefix[:1].upper()
            ec = {'L': _qrcode.constants.ERROR_CORRECT_L,
                  'M': _qrcode.constants.ERROR_CORRECT_M,
                  'Q': _qrcode.constants.ERROR_CORRECT_Q,
                  'H': _qrcode.constants.ERROR_CORRECT_H}.get(level, _qrcode.constants.ERROR_CORRECT_M)
            try:
                qr = _qrcode.QRCode(version=None, error_correction=ec, box_size=1, border=0)
                qr.add_data(content)
                qr.make(fit=True)
                matrix = [list(row) for row in qr.get_matrix()]
            except Exception:
                matrix = self._qr_schematic()
        else:
            matrix = self._qr_schematic()
        for _ in range(rotation // 90):
            matrix = [list(row) for row in zip(*matrix[::-1])]
        if len(self._qr_cache) > 80:
            self._qr_cache.clear()
        self._qr_cache[key] = matrix
        return matrix

    @staticmethod
    def _qr_schematic():
        n = 21
        matrix = [[False] * n for _ in range(n)]
        for fx, fy in ((0, 0), (n - 7, 0), (0, n - 7)):
            for yy in range(7):
                for xx in range(7):
                    border = xx in (0, 6) or yy in (0, 6)
                    center = 2 <= xx <= 4 and 2 <= yy <= 4
                    matrix[fy + yy][fx + xx] = border or center
        for y in range(n):
            for x in range(n):
                if any(fx <= x < fx + 8 and fy <= y < fy + 8
                       for fx, fy in ((0, 0), (n - 8, 0), (0, n - 8))):
                    continue
                matrix[y][x] = (x * 7 + y * 11 + x * y) % 5 < 2
        return matrix

    def render(self):
        if not hasattr(self, 'canvas'): return
        self.canvas.delete('all')
        self.resize_handles = {}
        dim = self.dimensions() if self.width_mm.get() and self.height_mm.get() else None
        if dim is None: return
        w, h = dim
        available_w = max(200, self.canvas.winfo_width()-60)
        available_h = max(200, self.canvas.winfo_height()-60)
        self.zoom = min(1.5, available_w/max(w,1), available_h/max(h,1))
        self.ox = 25; self.oy = 25
        self.canvas.create_rectangle(self.ox,self.oy,self.ox+w*self.zoom,self.oy+h*self.zoom,
                                     fill='white',outline='#667',width=2,tags=('paper',))
        for i, obj in enumerate(self.items):
            x = self.ox + obj['x']*self.zoom
            y = self.oy + obj['y']*self.zoom
            ww = obj['w']*self.zoom
            hh = obj['h']*self.zoom
            rotation = self._xg_rotation(obj) if obj['kind']=='text' else int(obj.get('rotation',0))
            tag = f'obj{i}'
            if rotation in (90,270): ww,hh = hh,ww
            kind = obj['kind']
            # Line orientation changes when rotated by 90 or 270 degrees.
            if kind in ('hline','vline') and rotation in (90,270):
                kind = 'vline' if kind == 'hline' else 'hline'
            if kind == 'hline':
                self.canvas.create_line(x,y+hh/2,x+ww,y+hh/2,fill='black',
                                        width=max(1,hh),tags=(tag,))
            elif kind == 'vline':
                self.canvas.create_line(x+ww/2,y,x+ww/2,y+hh,fill='black',
                                        width=max(1,ww),tags=(tag,))
            elif kind == 'box':
                self.canvas.create_rectangle(x,y,x+ww,y+hh,outline='black',width=2,tags=(tag,))
            elif kind == 'barcode':
                for b in range(max(1,int(ww//5))):
                    if b%3 != 1:
                        self.canvas.create_rectangle(x+b*5,y,x+b*5+2,y+hh*.75,
                                                     fill='black',outline='',tags=(tag,))
                self.canvas.create_text(x+ww/2,y+hh*.88,text=obj['text'][:30],
                                        angle=-rotation,font=('Arial',8),tags=(tag,))
            elif kind == 'qr':
                # ^BQ magnification means printer dots per module, NOT a
                # user-specified object width. Include the 4-module quiet zone
                # as a light outline so the user can see the occupied area.
                matrix = self._qr_matrix(obj)
                n = len(matrix)
                module_px = max(0.05, int(obj.get('qr_mag', 7)) * self.zoom)
                quiet = 4 * module_px
                side = (n + 8) * module_px
                ww = hh = side
                self.canvas.create_rectangle(x,y,x+side,y+side,
                                             fill='white',outline='#999',tags=(tag,))
                # Merge adjacent dark modules on each row to keep Tk responsive.
                for my,row in enumerate(matrix):
                    mx = 0
                    while mx < n:
                        if not row[mx]:
                            mx += 1
                            continue
                        start = mx
                        while mx < n and row[mx]:
                            mx += 1
                        x1 = x + quiet + start * module_px
                        x2 = x + quiet + mx * module_px
                        y1 = y + quiet + my * module_px
                        y2 = y1 + module_px
                        self.canvas.create_rectangle(x1,y1,x2,y2,
                                                     fill='black',outline='',tags=(tag,))
                # Finder patterns visibly move when the rotation changes.
            else:
                # Canvas text rotation is around the text anchor, not the ZPL field origin.
                # Use a centered anchor and compute a footprint from font metrics.
                font = self._preview_font(obj)
                content = obj.get('text','')
                tw = max(1,font.measure(content))
                th = max(1,font.metrics('linespace'))
                rotated_w,rotated_h = (th,tw) if rotation in (90,270) else (tw,th)
                self.canvas.create_text(x+rotated_w/2,y+rotated_h/2,text=content,
                                        anchor='center',angle=-rotation,font=font,tags=(tag,))
            if i in self.selected_indices:
                if kind in ('text','native_text'):
                    bbox = self.canvas.bbox(tag)
                    if bbox:
                        left,top,right,bottom = bbox
                    else:
                        left,top,right,bottom = x,y,x+ww,y+hh
                else:
                    left,top,right,bottom = x,y,x+ww,y+hh
                self.canvas.create_rectangle(left-3,top-3,right+3,bottom+3,
                                             outline='#2276da',dash=(4,3),tags=(tag,'selection'))
                if obj['kind'] in ('box','hline','vline'):
                    # A resize handle at the bottom-right of the visible footprint.
                    hx,hy = right,bottom
                    handle = self.canvas.create_rectangle(hx-6,hy-6,hx+6,hy+6,
                                        fill='#2276da',outline='white',width=1,
                                        tags=('resize_handle',f'resize{i}'))
                    self.resize_handles[handle] = i
        self.refresh_list()
        self._refresh_alignment_references()
        self.status.set(f'{len(self.items)} 個物件 | 標籤 {w} × {h} dots | 未解析指令段落 {len(self.unknown)}')

    def on_ctrl_down(self,event):
        index=self._hit_index(event)
        if index is not None:
            selected=set(self.selected_indices)
            if index in selected:selected.remove(index)
            else:selected.add(index)
            self.select(min(selected) if selected else None,selected)
            self.render()
        return 'break'

    def _hit_index(self,event):
        for hit in reversed(self.canvas.find_overlapping(event.x-2,event.y-2,event.x+2,event.y+2)):
            for tag in self.canvas.gettags(hit):
                if re.fullmatch(r'obj\d+',tag):return int(tag[3:])
        return None

    def on_down(self,event):
        hits=self.canvas.find_overlapping(event.x-7,event.y-7,event.x+7,event.y+7)
        for hit in reversed(hits):
            if hit in self.resize_handles:
                index=self.resize_handles[hit]
                self.select(index)
                self.drag={'mode':'resize','index':index,'x':event.x,'y':event.y,'start':self.items[index].copy()}
                return
        index=self._hit_index(event)
        if index is None:
            self.select(None)
            self.drag={'mode':'marquee','x':event.x,'y':event.y,'end_x':event.x,'end_y':event.y}
        else:
            if index not in self.selected_indices:self.select(index)
            self.drag={'mode':'move','x':event.x,'y':event.y,
                       'starts':{i:self.items[i].copy() for i in self.selected_indices}}
        self.render()

    def on_move(self,event):
        if not self.drag:return
        mode=self.drag['mode']
        if mode=='marquee':
            self.drag['end_x']=event.x;self.drag['end_y']=event.y
            self.render()
            self.canvas.create_rectangle(self.drag['x'],self.drag['y'],event.x,event.y,
                                         outline='#1876d2',dash=(3,3),fill='#b3d7ff',stipple='gray50',tags=('marquee',))
            return
        dx=round((event.x-self.drag['x'])/self.zoom)
        dy=round((event.y-self.drag['y'])/self.zoom)
        if mode=='move':
            for i,original in self.drag['starts'].items():
                self.items[i]['x']=original['x']+dx
                self.items[i]['y']=original['y']+dy
        elif mode=='resize':
            index=self.drag['index'];obj=self.items[index];original=self.drag['start']
            dw,dh=(dy,dx) if int(original.get('rotation',0)) in (90,270) else (dx,dy)
            if obj['kind']=='box':
                obj['w']=max(1,original['w']+dw);obj['h']=max(1,original['h']+dh)
            elif obj['kind']=='hline':obj['w']=max(1,original['w']+dw)
            elif obj['kind']=='vline':obj['h']=max(1,original['h']+dh)
        self.render()

    def on_up(self,event):
        if self.drag and self.drag['mode']=='marquee':
            x1,x2=sorted((self.drag['x'],event.x));y1,y2=sorted((self.drag['y'],event.y))
            selected=set()
            for i,obj in enumerate(self.items):
                x=self.ox+obj['x']*self.zoom;y=self.oy+obj['y']*self.zoom
                w=obj['w']*self.zoom;h=obj['h']*self.zoom
                if int(obj.get('rotation',0)) in (90,270):w,h=h,w
                if x<x2 and x+w>x1 and y<y2 and y+h>y1:selected.add(i)
            self.select(min(selected) if selected else None,selected)
        self.drag=None
        self.render()

    def _ensure_ini(self,obj):
        if obj['kind'] not in ('text','barcode','qr'):return
        if 'ini' not in obj:
            base={'DATA LENGTH':'40','ROTATE':''}
            if obj['kind']=='text':base.update({'PROMPT':'NAME','FONT NAME':'arial bold','FONT SIZE':'54'})
            obj['ini']=base

    @staticmethod
    def _xg_rotation(obj):
        """For XG, rotation is supplied by the company's INI, not ZPL."""
        raw = str(obj.get('ini', {}).get('ROTATE', '')).strip()
        if raw == '':
            return 0
        try:
            angle = int(raw)
        except ValueError:
            return 0
        return angle if angle in (0, 90, 180, 270) else 0

    def _load_ini_props(self):
        if not hasattr(self,'ini_props'):return
        obj=self.items[self.selected] if self.selected is not None else None
        if obj:self._ensure_ini(obj)
        for k,v in self.ini_props.items():v.set(str((obj or {}).get('ini',{}).get(k,'')))

    def apply_ini_props(self):
        if self.selected is None:return
        obj=self.items[self.selected]
        if obj['kind'] not in ('text','barcode','qr'):
            messagebox.showinfo('INI 屬性','此物件沒有 ITEM 編號。');return
        self._ensure_ini(obj)
        new_ini={k:v.get() for k,v in self.ini_props.items() if v.get() or k in ('DATA LENGTH','ROTATE')}
        if obj['kind']=='text':
            angle=new_ini.get('ROTATE','').strip()
            if angle not in ('','0','90','180','270'):
                messagebox.showerror('INI 旋轉角度錯誤','XG 文字 ROTATE 只接受空白、0、90、180、270。')
                return
            obj['rotation']=int(angle or 0)
            self.props['rotation'].set(str(obj['rotation']))
        obj['ini']=new_ini
        self.render()

    def _renumber_items(self):
        """Compact all dynamic field IDs in their canvas order; PQ follows the last field."""
        n=1
        for obj in self.items:
            if obj['kind'] in ('text','barcode','qr'):
                obj['text']=f'ITEM{n:04d}'
                self._ensure_ini(obj)
                n+=1
        self.next_item_number=n
        self.pq_placeholder=f'ITEM{n:04d}'

    def generate_ini(self,basename):
        # Write keys exactly as the company sample, preserving spaces and case.
        def clean(v):return str(v).replace('\r',' ').replace('\n',' ')
        rows=['[SETUP]']
        setup_order=['Printer Model','OUTPORT','BAUD RATE','STOP BITS','DATA BIT','Parity']
        for key in setup_order:rows.append(f'{key}={clean(self.ini_setup.get(key,""))}')
        rows.extend([f'Format file Path={basename}.fmt',f'Text   file Path={basename}.txt'])
        for key in ('Output file Path','LOGO   file Path'):rows.append(f'{key}={clean(self.ini_setup.get(key,""))}')
        rows.extend([f'Field Delimiter={clean(self.field_delimiter.get())}',f'Record Delimiter={clean(self.record_delimiter.get())}'])
        for key in ('PagePreambleFile','PagePostambleFile','Form Show'):rows.append(f'{key}={clean(self.ini_setup.get(key,""))}')
        rows.extend(['','[PROGRAM]',f'NAME={clean(self.ini_program.get())}'])
        for obj in self.items:
            if obj['kind'] not in ('text','barcode','qr'):continue
            self._ensure_ini(obj)
            rows.extend(['',f'[{obj["text"]}]'])
            ini=obj['ini']
            for key in ('DATA LENGTH','PROMPT','FONT NAME','FONT SIZE','ROTATE'):
                if key in ini:rows.append(f'{key}={clean(ini[key])}')
            for key,val in ini.items():
                if key not in ('DATA LENGTH','PROMPT','FONT NAME','FONT SIZE','ROTATE'):
                    rows.append(f'{clean(key)}={clean(val)}')
        rows.extend(['',f'[{self.next_pq_name()}]','DATA LENGTH=4','PROMPT=QTY',''])
        return '\n'.join(rows)

    def project_data(self):
        """One canonical representation for manual save and export sidecar."""
        return {
            'width_mm': self.width_mm.get(),
            'height_mm': self.height_mm.get(),
            'width_dots': int(self.width_dots.get()),
            'height_dots': int(self.height_dots.get()),
            'dimension_unit': self.dimension_unit.get(),
            'dimension_source': self.dimension_source,
            'dimension_exact': self.dimension_exact,
            'dpi': int(self.dpi.get()),
            'items': self.items,
            'unparsed': self.unknown,
            'next_item_number': self.next_item_number,
            'label_home': list(self.label_home),
            'pq_placeholder': self.pq_placeholder,
            'field_delimiter':self.field_delimiter.get(),
            'record_delimiter':self.record_delimiter.get(),
            'ini_program':self.ini_program.get(),
            'ini_setup':self.ini_setup,
            'ini_extra':self.ini_extra,
        }

    def save_project(self):
        if not self.apply_dimensions():
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.json', filetypes=[('Designer JSON', '*.json')]
        )
        if path:
            try:
                Path(path).write_text(
                    json.dumps(self.project_data(), ensure_ascii=False, indent=2),
                    encoding='utf-8'
                )
            except OSError as exc:
                messagebox.showerror('儲存失敗', str(exc))

    def open_project(self):
        path=filedialog.askopenfilename(filetypes=[('Designer JSON','*.json')])
        if not path:return
        try:
            data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
            legacy_dpi=int(data.get('dpi',300))
            if legacy_dpi != 300:
                messagebox.showwarning('舊專案 DPI 不相容',f'此專案使用 {legacy_dpi} DPI，目前版本僅支援 300 DPI。\n為避免位置與尺寸錯誤，已取消開啟；請先使用舊版處理。')
                return
            self.width_mm.set(data['width_mm']);self.height_mm.set(data['height_mm']);self.dpi.set(300)
            self.width_dots.set(str(data.get('width_dots',self.mm_to_dots(self.width_mm.get(),self.dpi.get()))))
            self.height_dots.set(str(data.get('height_dots',self.mm_to_dots(self.height_mm.get(),self.dpi.get()))))
            self.dimension_source=data.get('dimension_source','mm')
            self.dimension_exact=bool(data.get('dimension_exact',True))
            self.dimension_unit.set(data.get('dimension_unit','mm'));self._dimension_note()
            self._last_applied=(self.dimension_unit.get(),self.width_mm.get(),self.height_mm.get(),self.width_dots.get(),self.height_dots.get(),int(self.dpi.get()))
            self.label_home=tuple(data.get('label_home',[0,0]));self.pq_placeholder=data.get('pq_placeholder')
            self.field_delimiter.set(data.get('field_delimiter',','));self.record_delimiter.set(data.get('record_delimiter',''))
            self.ini_program.set(data.get('ini_program','TA-TAN CARD PROGRAM'))
            self.ini_setup.update(data.get('ini_setup',{}));self.ini_extra=data.get('ini_extra',{})
            self.items=data['items'];
            for obj in self.items:
                obj.setdefault('rotation',0)
                had_ini_rotate = 'ini' in obj and 'ROTATE' in obj['ini']
                self._ensure_ini(obj)
                if obj['kind']=='text':
                    if not had_ini_rotate and int(obj.get('rotation',0)) in (90,180,270):
                        obj['ini']['ROTATE']=str(obj['rotation'])
                    obj['rotation']=self._xg_rotation(obj)
            self.unknown=data.get('unparsed',[]);self.next_item_number=self._next_number()
            self.select(None);self.render()
        except (OSError,ValueError,KeyError,TypeError) as e:messagebox.showerror('開啟失敗',str(e))

    def _next_number(self):
        nums=[int(m.group(1)) for o in self.items if (m:=re.fullmatch(r'ITEM(\d+)',str(o.get('text',''))))]
        return max(nums,default=0)+1

    @staticmethod
    def safe_value(value):
        """Prevent ZPL control injection through editor fields."""
        return str(value).replace('^',' ').replace('~',' ').replace('\r',' ').replace('\n',' ')

    def next_pq_name(self):
        """Next placeholder after existing ITEM fields; not the numeric print count."""
        names = [int(m.group(1)) for o in self.items
                 if (m := re.fullmatch(r'ITEM(\d+)', str(o.get('text',''))))]
        last = max(names, default=0)
        return f'ITEM{last+1:04d}'

    def zpl(self):
        dim=self.dimensions()
        if dim is None:return None
        w,h=dim
        lhx,lhy=self.label_home
        lines=['^XA',f'^LH{lhx},{lhy}^FS',f'^PW{w}',f'^LL{h}']
        for o in self.items:
            x,y,ww,hh=(int(o[k]) for k in ('x','y','w','h'))
            value=self.safe_value(o.get('text',''))
            rot={0:'N',90:'R',180:'I',270:'B'}[int(o.get('rotation',0))]
            if o['kind']=='native_text':
                lines.append(f'^FO{x},{y}^A0{rot},{hh},{ww}^FD{value}^FS')
            elif o['kind']=='text':
                lines.append(f'^FO{x},{y}^XG{value},{int(o.get("xg_x",1))},{int(o.get("xg_y",1))}^FS')
            elif o['kind']=='barcode':
                by=f'^BY{int(o.get("by_width",2))},{int(o.get("by_ratio",3))},{int(o.get("by_height",40))}'
                orient=str(o.get('bc_orientation',''))
                if orient not in ('','N','R','I','B'): orient=''
                # Preserve the company's ^BC,Y,N,N form for unrotated fields.
                if int(o.get('rotation',0)) != 0: orient=rot
                bc=f'^BC{orient},{o.get("bc_print","Y")},{o.get("bc_above","N")},{o.get("bc_check","N")}'
                lines.append(f'^FO{x},{y}{by}{bc}^FD{value}^FS')
            elif o['kind']=='qr':
                model=int(o.get('qr_model',2)); mag=int(o.get('qr_mag',7))
                prefix=str(o.get('qr_prefix','M,'))
                if prefix not in ('M,','LA,','MA,','MH,','L,','H,','Q,'): prefix='M,'
                lines.append(f'^FO{x},{y}^BQ{rot},{model},{mag}^FD{prefix}{value}^FS')
            elif o['kind'] in ('box','hline','vline'):
                if rot in ('R','B'):ww,hh=hh,ww
                thickness=int(o.get('thickness',2 if o['kind']=='box' else min(ww,hh)))
                if o['kind'] in ('hline','vline'): thickness=min(thickness,ww,hh)
                lines.append(f'^FO{x},{y}^GB{ww},{hh},{thickness}^FS')
        lines.append(f'^PQ{self.next_pq_name()}')
        lines.append('^XZ')
        return '\n'.join(lines)+'\n'

    def generate_txt_fields(self):
        """Company TXT payload: dynamic field placeholders in ZPL/INI order.

        Includes the final ^PQ QTY placeholder because it is also an INI ITEM.
        """
        delimiter = self.field_delimiter.get()
        if delimiter not in (',', ';', ':'):
            raise ValueError('欄位分隔符僅支援 ,、; 或 :，請先在 INI 設定選擇。')
        fields = [str(obj.get('text', '')) for obj in self.items
                  if obj.get('kind') in ('text', 'barcode', 'qr')]
        fields.append(self.next_pq_name())
        return delimiter.join(fields) + '\n'

    def export_zpl(self):
        if self.unknown:
            messagebox.showwarning('匯出已停用',
                '匯入檔案包含未解析的 ZPL 指令，為避免遺失原始設定，本版禁止直接匯出。')
            return
        if not self.apply_dimensions():
            return
        data = self.zpl()
        if data is None:
            return
        selected = filedialog.asksaveasfilename(
            title='選擇匯出檔名（建立 FMT、TXT、JSON、INI）',
            defaultextension='.fmt',
            filetypes=[('FMT 標籤格式', '*.fmt'), ('TXT 文字檔', '*.txt')]
        )
        if not selected:
            return
        base = Path(selected)
        if base.suffix.lower() in ('.fmt', '.txt', '.json', '.ini'):
            base = base.with_suffix('')
        paths = [base.with_suffix(ext) for ext in ('.fmt', '.txt', '.json', '.ini')]
        existing = [p for p in paths if p.exists()]
        if existing and not messagebox.askyesno(
            '確認覆蓋', '以下檔案已存在，確定覆蓋？\n' + '\n'.join(map(str, existing))
        ):
            return
        try:
            project = json.dumps(self.project_data(), ensure_ascii=False, indent=2)
            txt_bytes = self.generate_txt_fields().encode('cp950', errors='strict')
            paths[0].write_text(data, encoding='utf-8')
            # Windows Traditional Chinese 'ANSI' is generally CP950 (Big5).
            # Use strict encoding so unsupported characters cannot silently change.
            paths[1].write_bytes(txt_bytes)
            paths[2].write_text(project, encoding='utf-8')
            paths[3].write_text(self.generate_ini(base.name), encoding='utf-8-sig')
        except (OSError, ValueError, TypeError, UnicodeError) as exc:
            messagebox.showerror('匯出失敗', f'寫入檔案時發生錯誤：{exc}\n請檢查是否有部分檔案已寫入。')
            return
        messagebox.showinfo('匯出完成',
            '已建立：\n' + '\n'.join(p.name for p in paths)
            + '\n\nTXT 是依照 INI 欄位分隔符產生的 ITEM 清單（含 QTY），使用 ANSI CP950；FMT 為 ZPL。請先測試。')

    @staticmethod
    def parse_zpl(raw):
        """Parse supported company ZPL dialect; collect unknown tokens safely."""
        raw = re.sub(r'(?m)^\s*#\s?', '', raw)  # pasted sample prefixes
        objects=[]; unknown=[]
        fields=list(re.finditer(r'\^FO(-?\d+),(-?\d+)(.*?)(?=\^FO|\^PQ|\^XZ|$)',raw,re.S))
        for match in fields:
            x,y=int(match.group(1)),int(match.group(2))
            segment=match.group(3).strip()
            common={'x':x,'y':y,'rotation':0}
            gx=re.fullmatch(r'\^XG([^\^~]+?),(\d+),(\d+)\^FS',segment,re.S)
            bc=re.fullmatch(r'\^BY(\d+),(\d+),(\d+)\^BC([NRIB]?),(Y|N),(Y|N),(Y|N)\^FD(.*?)\^FS',segment,re.S)
            qr=re.fullmatch(r'\^BQ([NRIB]),([12]),(\d+)\^FD((?:[LMQH]A?,))(.*?)\^FS',segment,re.S)
            gb=re.fullmatch(r'\^GB(\d+),(\d+),(\d+)\^FS',segment,re.S)
            native=re.fullmatch(r'\^A0([NRIB]),(\d+),(\d+)\^FD(.*?)\^FS',segment,re.S)
            if gx:
                objects.append(dict(common,kind='text',text=gx.group(1),w=170,h=45,xg_x=int(gx.group(2)),xg_y=int(gx.group(3))))
            elif bc:
                bw,ratio,bheight=map(int,bc.group(1,2,3)); orient=bc.group(4)
                objects.append(dict(common,kind='barcode',text=bc.group(8),w=170,h=bheight,
                                    rotation={'N':0,'R':90,'I':180,'B':270,'':0}[orient],
                                    by_width=bw,by_ratio=ratio,by_height=bheight,bc_orientation=orient,
                                    bc_print=bc.group(5),bc_above=bc.group(6),bc_check=bc.group(7)))
            elif qr:
                mag=int(qr.group(3))
                objects.append(dict(common,kind='qr',text=qr.group(5),w=max(40,mag*14),h=max(40,mag*14),
                                    rotation={'N':0,'R':90,'I':180,'B':270}[qr.group(1)],
                                    qr_model=int(qr.group(2)),qr_mag=mag,qr_prefix=qr.group(4)))
            elif native:
                orient,hh,ww,value=native.groups()
                objects.append(dict(common,kind='native_text',text=value,w=int(ww),h=int(hh),
                                    rotation={'N':0,'R':90,'I':180,'B':270}[orient]))
            elif gb:
                ww,hh,thick=map(int,gb.groups())
                kind='hline' if thick==hh and ww>hh else 'vline' if thick==ww and hh>ww else 'box'
                objects.append(dict(common,kind=kind,text='',w=ww,h=hh,thickness=thick))
            else:
                unknown.append(match.group(0))
        remaining=re.sub(r'\^FO-?\d+,-?\d+.*?(?=\^FO|\^PQ|\^XZ|$)','',raw,flags=re.S)
        remaining=re.sub(r'\^XA|\^XZ|\^LH-?\d+,-?\d+\^FS?|\^PW\d+|\^LL\d+|\^PQ(?:ITEM\d+|\d+)|\s+','',remaining)
        if remaining:unknown.append(remaining)
        return objects,unknown

    def open_zpl(self):
        path=filedialog.askopenfilename(filetypes=[('ZPL 文字檔','*.zpl *.txt *.fmt'),('所有檔案','*.*')])
        if not path:return
        try:
            raw=Path(path).read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:
            try:raw=Path(path).read_text(encoding='cp950')
            except UnicodeError:
                messagebox.showerror('編碼不支援','檔案不是可辨識的 UTF-8 / CP950 文字檔');return
        except OSError as e:messagebox.showerror('讀取失敗',str(e));return
        self.items,self.unknown=self.parse_zpl(raw)
        self.selected_indices=set()
        lh=re.search(r'\^LH(-?\d+),(-?\d+)',raw)
        self.label_home=(int(lh.group(1)),int(lh.group(2))) if lh else (0,0)
        pq=re.search(r'\^PQ(ITEM\d+|\d+)',raw)
        self.pq_placeholder=pq.group(1) if pq and pq.group(1).startswith('ITEM') else None
        pw=re.search(r'\^PW(\d+)',raw);ll=re.search(r'\^LL(\d+)',raw)
        if pw:self.width_dots.set(pw.group(1));self.width_mm.set(self.fmt_mm(self.dots_to_mm(int(pw.group(1)),self.dpi.get())))
        if ll:self.height_dots.set(ll.group(1));self.height_mm.set(self.fmt_mm(self.dots_to_mm(int(ll.group(1)),self.dpi.get())))
        self.dimension_source='dots';self.dimension_exact=False;self._dimension_note()
        self._last_applied=(self.dimension_unit.get(),self.width_mm.get(),self.height_mm.get(),self.width_dots.get(),self.height_dots.get(),int(self.dpi.get()))
        self.next_item_number=self._next_number();
        for obj in self.items:self._ensure_ini(obj)
        self.select(None);self.render()
        messagebox.showinfo('匯入結果',f'已解析 {len(self.items)} 個物件。\n未解析段落：{len(self.unknown)}。\n本版匯入是有限支援；請勿直接覆蓋公司原始檔。')

    def open_ini(self):
        path=filedialog.askopenfilename(filetypes=[('INI 設定檔','*.ini'),('所有檔案','*.*')])
        if not path:return
        config=configparser.ConfigParser(interpolation=None,strict=False)
        config.optionxform=str
        try:
            try:
                raw=Path(path).read_text(encoding='utf-8-sig')
            except UnicodeDecodeError:
                raw=Path(path).read_text(encoding='cp950')
            try:config.read_string(raw)
            except configparser.Error:
                raw=Path(path).read_text(encoding='cp950')
                config.read_string(raw)
            if config.has_section('SETUP'):
                setup=dict(config.items('SETUP'))
                self.field_delimiter.set(setup.get('Field Delimiter',','))
                self.record_delimiter.set(setup.get('Record Delimiter',''))
                self.ini_setup.update({k:v for k,v in setup.items() if k not in ('Field Delimiter','Record Delimiter','Format file Path','Text   file Path')})
            if config.has_section('PROGRAM'):
                self.ini_program.set(config.get('PROGRAM','NAME',fallback='TA-TAN CARD PROGRAM'))
            mapped=0
            for obj in self.items:
                if obj['kind'] in ('text','barcode','qr') and config.has_section(obj.get('text','')):
                    obj['ini']=dict(config.items(obj['text']));mapped+=1
                    if obj['kind']=='text':obj['rotation']=self._xg_rotation(obj)
            self._load_ini_props()
            messagebox.showinfo('INI 匯入',f'已載入設定；套用到 {mapped} 個目前畫布的 ITEM。\n若尚未匯入 FMT，請先匯入 FMT，再重新開啟 INI。')
        except (OSError,configparser.Error,UnicodeError) as e:messagebox.showerror('讀取失敗',str(e))

if __name__=='__main__':
    Designer().mainloop()
