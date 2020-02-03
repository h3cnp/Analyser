#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import re
import configparser
from bitarray import bitarray

from PyQt5 import QtCore, QtGui, QtWidgets

# 配置文件
TEMPLATE_FILE = 'template.ini'


###################################################################################################

def Str2Int(s):
    if s == '':
        return 0
    elif s.startswith('0x'):
        return int(s, 16)
    elif s.startswith('0'):
        return int(s, 8)
    else:
        return int(s, 10)


def ParseConfigValue(cfg_value):
    """
    解析配置文件中字段的描述信息
    cfg_value可能的格式如下
         1
         1          =   1
         8 : 10
         8 : 10     =   7
        16 : 31
        16 : 31     =   0x0800
    
    函数返回truple
        (DEFAULT_VALUE, START_OFFSET, END_OFFSET)
    """
    # 删除所有whitespace characters (space, tab, newline, and so on), 并尝试以'='分割字符串
    pattern = re.compile(r'\s+')
    ss = re.sub(pattern, '', cfg_value).split('=')

    if len(ss) > 1:
        default_value = Str2Int(ss[1])
    else:
        default_value = 0

    offsets = ss[0].split(':')
    start_offset = Str2Int(offsets[0])
    if len(offsets) > 1:
        end_offset = Str2Int(offsets[1])
    else:
        end_offset = start_offset

    # start_offset必须要不大于end_offset
    if start_offset > end_offset:
        start_offset, end_offset = end_offset, start_offset

    return (default_value, start_offset, end_offset)


"""
读取ini配置文件
"""
def ReadTemplate(file):
    templates = {}

    cfg = configparser.ConfigParser()
    cfg.read(file)

    for section in cfg.sections():
        fields = {}
        for field, value in cfg.items(section):
            fields[field] = ParseConfigValue(value)
        templates[section] = fields
    
    return templates


###################################################################################################

"""
bit视图类
"""
class BitView(QtWidgets.QToolButton):
    # bit值翻转信号
    bitFlipped = QtCore.pyqtSignal(int, int)

    def __init__(self, parent=None, index=0, isset=False):
        super().__init__(parent)
        self.index = index
        self.setBitValue(isset)

        font = QtGui.QFont()
        font.setFamily('Arial')
        font.setPointSize(10)
        font.setBold(True)
        self.setFont(font)
        self.setAutoRaise(True)

        # 设置bit点击事件处理函数
        self.clicked.connect(self.onBitClicked)

    def setBitValue(self, isset):
        self.value = isset
        if isset:
            self.setText('1')
        else:
            self.setText('0')
        
    def getBitValue(self):
        return int(self.value)

    def isBitSet(self):
        return self.value

    def onBitClicked(self):
        """
        点击一下，bit值翻转一次：
            0 -> 1
            1 -> 0
            ...
        """
        self.setBitValue(bool(1 - self.value)) # bit值翻转
        # bit值发生变化，发送信号
        self.bitFlipped.emit(self.index, int(self.value))


###################################################################################################

"""
32-bit 寄存器视图类
"""
class Reg32View(QtWidgets.QGroupBox):

    reg32ValueChanged = QtCore.pyqtSignal(int, int)

    def __init__(self, parent=None, dword=0):
        super().__init__(parent)

        # 当前长字索引
        self.dword = dword
        # bit数组, 保存每个bit的值（True/False）
        self.reg32bits = bitarray(32)
        self.reg32bits.setall(False)
        # bit视图
        self.reg32bitviews = [None for i in range(0, 32)]

        # bitarray的索引(array_index)与regview索引(bit_index)的关系为
        #   array_index = 31 - bit_index
        #
        #           offset
        # bitarray: 0   1   2   3   ...     31
        #
        # regview:  31  30  29  28  ...     0

        self.initUi()

    def initUi(self):
        font = QtGui.QFont()
        font.setFamily('Arial')

        self.setFont(font)
        self.setTitle(f'DWORD {self.dword} inspection')

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(0)
        self.setLayout(grid)

        for array_index in range(0, 32):
            bit_index = 31 - array_index
            # bit偏移，只显示4的整数倍偏移
            if bit_index % 4 == 0:
                offset = QtWidgets.QLabel('{}'.format(bit_index), self)
                offset.setAlignment(QtCore.Qt.AlignCenter)
                offset.setFont(font)
                grid.addWidget(offset, 0, array_index)

            # bit
            bit = BitView(index=bit_index, isset=self.reg32bits[array_index])
            bit.bitFlipped.connect(self.onReg32BitChanged)
            self.reg32bitviews[bit_index] = bit
            grid.addWidget(bit, 1, array_index)

        setall = QtWidgets.QPushButton()
        setall.setText('Set All')
        setall.setFont(font)
        setall.clicked.connect(self.onReg32SetAll)
        grid.addWidget(setall, 0, 32)

        clearall = QtWidgets.QPushButton()
        clearall.setText('Clear All')
        clearall.setFont(font)
        clearall.clicked.connect(self.onReg32ClearAll)
        grid.addWidget(clearall, 1, 32)

    def update(self, dword, hexstr):
        if self.dword != dword:
            self.dword = dword
            self.setReg32Value(int(hexstr, 16))
            self.setTitle(f'DWORD {self.dword} inspection')

    def sendReg32ValueChanged(self):
        self.reg32ValueChanged.emit(self.dword, self.getReg32Value())

    def onReg32BitChanged(self, bit_index, bit_value):
        self.reg32bits[31 - bit_index] = bool(bit_value)  # 设置对应bit值
        self.sendReg32ValueChanged()
    
    def onReg32SetAll(self):
        # self.reg32bits.setall(True)
        self.setReg32Value(0xFFFFFFFF)
        self.sendReg32ValueChanged()
    
    def onReg32ClearAll(self):
        # self.reg32bits.setall(False)
        self.setReg32Value(0)
        self.sendReg32ValueChanged()

    def getReg32HexStr(self):
        """
        十六进制字符串
        """
        return self.reg32bits.tobytes().hex().upper()

    def getReg32Value(self):
        """
        int值
        """
        return int(self.getReg32HexStr(), 16)

    def setReg32Value(self, value):
        self.reg32bits = bitarray(f'{value:032b}')
        for bit_index in range(0, 32):
            self.reg32bitviews[bit_index].setBitValue(self.reg32bits[31 - bit_index])


###################################################################################################

"""
可点击的QLineEdit
鼠标点击选中4字节数据
"""
class InputEdit(QtWidgets.QLineEdit):

    clicked = QtCore.pyqtSignal(int, str)

    def __init__(self, s, parent=None):
        super().__init__(s, parent)
        self.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
        validator = QtGui.QRegExpValidator(QtCore.QRegExp("[0-9A-Fa-f]*"))
        self.setValidator(validator)
        font = QtGui.QFont()
        font.setFamily('Consolas')
        font.setPointSize(11)
        self.setFont(font)

        # self.setReadOnly(True)

    def mousePressEvent(self, event):
        QtWidgets.QLineEdit.mousePressEvent(self, event)
        pos = self.cursorPosition()
        if pos == len(self.text()):
            pos -= 1
        self.setSelection((pos >> 3) << 3, 8)
        self.clicked.emit((pos >> 3), self.selectedText())

    def updateHexStr(self, dword, value):
        value = value & 0xFFFFFFFF
        lvalue = list(f'{value:08X}')
        ltext = list(self.text())
        pos = dword << 3
        for i in range(0, 8):
            ltext[pos + i] = lvalue[i]
        self.setText(''.join(ltext))
        self.setSelection(pos, 8)

    def setDwordSelection(self, dword):
        self.setSelection(dword << 3, 8)
        self.clicked.emit(dword, self.selectedText())


###################################################################################################

"""
字段解析显示
"""
class FieldsView(QtWidgets.QTreeView):
    FIELD = 0
    START_OFFSET = 1
    END_OFFSET = 2
    VALUE = 3

    selectDword = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.bitarray = bitarray()

        self.model = QtGui.QStandardItemModel(0, 4)
        self.model.setHeaderData(self.FIELD, QtCore.Qt.Horizontal, "Field")
        self.model.setHeaderData(self.START_OFFSET, QtCore.Qt.Horizontal, "From Bit#")
        self.model.setHeaderData(self.END_OFFSET, QtCore.Qt.Horizontal, "To Bit#")
        self.model.setHeaderData(self.VALUE, QtCore.Qt.Horizontal, "Value")
        self.setModel(self.model)
        
        self.model.itemChanged.connect(self.onFieldValueChanged)
        self.clicked.connect(self.onFieldClicked)

    def parse(self, hexstr, template):
        # 解析过程中断开信号处理
        self.model.itemChanged.disconnect(self.onFieldValueChanged)

        # 先清除当前model中的所有数据(不使用clear()方法，因为clear会同时清除header)
        self.model.removeRows(0, self.model.rowCount())
        self.model.setRowCount(len(template))
        
        binstr = bin(int(hexstr, 16))[2:]
        binstr = binstr.zfill(len(hexstr)<<2)
        self.bitarray = bitarray(binstr)
        
        row = 0
        for field, info in template.items():
            value, start_offset, end_offset = info
            if start_offset == end_offset:
                value = str(int(self.bitarray[start_offset]))
                # value = self.bitarray[start_offset]
            else:
                value = '0x'+self.bitarray[start_offset:end_offset].tobytes().hex().upper()
                # value = int(self.bitarray[start_offset:end_offset].tobytes().hex(), 16)
            self.model.setData(self.model.index(row, self.VALUE), value, QtCore.Qt.DisplayRole)

            for col, val in zip([self.FIELD, self.START_OFFSET, self.END_OFFSET], [field, start_offset, end_offset]):
                item = QtGui.QStandardItem()
                item.setEditable(False)
                item.setData(val, QtCore.Qt.DisplayRole)
                self.model.setItem(row, col, item)

            row += 1

        # 恢复信号处理
        self.model.itemChanged.connect(self.onFieldValueChanged)

    def onFieldValueChanged(self, item):
        index = self.model.indexFromItem(item)
        print(index.row(), index.column(), item.data(QtCore.Qt.DisplayRole))

    def onFieldClicked(self, index):
        data = self.model.itemData(self.model.index(index.row(), self.START_OFFSET))
        dword = data[0] >> 5    # 1个长字（4字节）有32bits
        self.selectDword.emit(dword)


###################################################################################################

"""
主窗口
"""
class AnalyserUi(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.templates = ReadTemplate(TEMPLATE_FILE)

        self.hexstr = 'ABCDEF0123456789ABCDEF0123456789'
        self.bytesize = len(self.hexstr) >> 1
        self.dwordsize = self.bytesize >> 2

        self.initUi()

        self.reg32view.reg32ValueChanged.connect(self.inputview.updateHexStr)
        self.inputview.clicked.connect(self.reg32view.update)
        self.fieldsview.parse(self.inputview.text(), self.templates['IPCT_RESULT'])
        self.fieldsview.selectDword.connect(self.inputview.setDwordSelection)

        self.show()

    def initUi(self):
        # self.setWindowFlags(QtCore.Qt.MSWindowsFixedSizeDialogHint)
        centralwidget = QtWidgets.QWidget(self)
        self.setCentralWidget(centralwidget)

        font = QtGui.QFont()
        font.setFamily('Arial')
        # font.setPointSize(11)
   
        toolbar = QtWidgets.QToolBar(self)
        self.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)
        actionPaste = QtWidgets.QAction(self)
        actionPaste.setText("Paste")
        actionPaste.setFont(font)
        toolbar.addAction(actionPaste)
        actionCopy = QtWidgets.QAction(self)
        actionCopy.setText("Copy")
        actionCopy.setFont(font)
        toolbar.addAction(actionCopy)

        grid = QtWidgets.QGridLayout()
        grid.setVerticalSpacing(16)
        centralwidget.setLayout(grid)
  
        self.inputview = InputEdit(self.hexstr)
        grid.addWidget(self.inputview, 0, 0, 1, 3)
        self.inputview.setSelection(0, 8)
        
        self.reg32view = Reg32View(self)
        grid.addWidget(self.reg32view, 1, 0, 1, 3)
        
        selectorl = QtWidgets.QLabel('Struct')
        self.selector = QtWidgets.QComboBox()
        grid.addWidget(selectorl, 2, 0)
        grid.addWidget(self.selector, 2, 1)
        selectorl.setFont(font)
        self.selector.setEditable(True)
        self.selector.setFont(font)
        self.selector.addItems(list(self.templates))    # 模板添加到下拉列表中

        self.fieldsview = FieldsView()
        grid.addWidget(self.fieldsview, 2, 2, 2, 1)
        # self.treemodel = QtGui.QStandardItemModel(0, 3)
        # self.treemodel.setHorizontalHeaderLabels(['Field', 'Offset', 'Value'])
        # self.treeview.setModel(self.treemodel)


###################################################################################################

if __name__ == '__main__':
    # t = ReadTemplate(TEMPLATE_FILE)
    # print(t)

    app = QtWidgets.QApplication(sys.argv)
    ex = AnalyserUi()
    # ex = Reg32View()
    # ex.setReg32Value(0xABCDEF)
    # ex.show()
    sys.exit(app.exec_())



