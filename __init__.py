# -*- coding: utf-8 -*-
######################################################################################
# Source code highlighter for wikipad
# This a bridge for the Pygments library (http://pygments.org)
# version 1.02
#
# Installation:
# * check the version of python used by wiki (2.4 for the binary distributions)
# * get the latest egg for pygments at http://pypi.python.org/pypi/Pygments
# * go the folder extension of your wikipad distribution/sources. Create a sub-folder "lib"
# * copy the pygments egg to the new sub-folder
# * if you are using a binary distribution, you may have also to copy the python modules:
#    = "commands" (http://svn.python.org/view/*checkout*/python/trunk/Lib/commands.py)
#    = "HTMLParser" (http://svn.python.org/view/*checkout*/python/trunk/Lib/HTMLParser.py)
#    = "markupbase" (http://svn.python.org/view/*checkout*/python/trunk/Lib/markupbase.py)
#
# Usage:
# * wiki syntax: "[:pc:/// .....code..... :::options1=val1;options2=val2;...///]"
# * options:
#      * lang: the name of the programming language (see the plugin options panel for a list of these) (default: see the plugin options panel)
#      * showLines: 0 if the line numbers should not be displayed, a non-zero value otherwise (default: see the plugin options panel)
#      * startLine: the number of the first line  (default: 1)
#      * hlLines: a comma separated list of line numbers to highlight (default: none)
#      * bkg: the Id of a background defined in the options panel, 
#           "default" for the default background (or no bkg option), 
#            an empty string for no background
#  * menu entries:
#      * paste the clipboard contents as a code with the default options set in the plugin options panel
#      * surround the selection with the appropriate tags, option values are the default options set in the plugin options panel
#
# ChangeLog:
#  * 24 Mar. 2013 (Michael Butscher):
#     * Packed into ZIP file including pygments (modified to use relative imports only)
#     * Support for setting options in the appendices of the insertion
#  * 08 Nov. 2008: version 1.03
#     * make the changes in font color and style with the internal previewer
#       WARNING: there  is a new installation procedure for Pygments and other modules
#  * 02 Nov. 2008: version 1.02
#     * fixed line numbering
#     * added the Id "default" for the default background
#     * fixed bug which could add an extra empty line to the code with the menu commands
#  * 01 Nov. 2008: version 1.01
#     * Added support for custom backgrounds
#  * 26 Oct. 2008: first release
#
######################################################################################
import os, sys, glob, cStringIO, wx

# The APIs we expose
WIKIDPAD_PLUGIN = (
    ("MenuFunctions",1),
    ("InsertionByKey", 1), 
    ("Options", 1),
    )

INSERTION_TAG = u"pc"

SEP = u","
ESC_SEP = u",,"
DEFAULT_LANG = u"Python"
OPTION_LANG = "plugin_prettyCode_lang"
DEFAULT_SHOWLN = False
OPTION_SHOWLN = "plugin_prettyCode_ShowLN"
DEFAULT_BKGS = {
                u"Light Blue": u'background-color: #F7F9FA; border: 1px #8CACBB dashed; width: 80%; padding: 4px; margin: 2',
                u"Light Yellow": u'background-color: #FFFFDD; border: 1px #8CACBB dashed; width: 80%; padding: 4px; margin: 2',
                }
OPTION_BKGS = "plugin_prettyCode_Bkgs"
DEFAULT_BKG = _(u"Light Blue")
OPTION_BKG = "plugin_prettyCode_Bkg"
BKG_TMPL = u'background-color: #F7F9FA; border: 1px #8CACBB dashed; width: 80%; padding: 4px; margin: 2'
BKG_NEW = _(u"Bkg %d")
NO_BKG = _(u"None")

#####
# TODO: show and format exception report
#####

######################################################################################
# Pygments
######################################################################################
# the pygments module
pygments = None

def import_Pygments(app):
    """
    Load the Pygments library
    """
    global pygments
    from . import pygments

######################################################################################
# Options
######################################################################################
class Options(object):
    """
    The plugin options
    """
    @staticmethod
    def register(app):
        """
        Register the plugin options
        """
        app.getDefaultGlobalConfigDict()[("main", OPTION_LANG)] = DEFAULT_LANG
        app.getDefaultGlobalConfigDict()[("main", OPTION_SHOWLN)] = unicode(DEFAULT_SHOWLN)
        app.getDefaultGlobalConfigDict()[("main", OPTION_BKGS)] = unicode(DEFAULT_BKGS)
        app.getDefaultGlobalConfigDict()[("main", OPTION_BKG)] = DEFAULT_BKG
    def __init__(self, config):
        """
        Constructor
        """
        self.config = config
        self.lang = self.config.get("main", OPTION_LANG, DEFAULT_LANG)
        self.showLN = self.config.getboolean("main", OPTION_SHOWLN, DEFAULT_SHOWLN)
        self.bkgs = eval(self.config.get("main", OPTION_BKGS, unicode(DEFAULT_BKGS)))
        self.bkg = self.config.get("main", OPTION_BKG, DEFAULT_BKG)
        self.startLine = 1
        self.hlLines = []
    def save(self):
        """
        Save the plugin options
        """
        self.config.set("main", OPTION_LANG, self.lang)
        self.config.set("main", OPTION_SHOWLN, unicode(self.showLN))
        self.config.set("main", OPTION_BKGS, unicode(self.bkgs))
        self.config.set("main", OPTION_BKG, self.bkg)

######################################################################################
# Menus
######################################################################################
def describeMenuItems(wiki):
    """
    wiki -- Calling PersonalWikiFrame
    Returns a sequence of tuples to describe the menu items, where each must
    contain (in this order):
        - callback function
        - menu item string
        - menu item description (string to show in status bar)
    It can contain the following additional items (in this order), each of
    them can be replaced by None:
        - icon descriptor (see below, if no icon found, it won't show one)
        - menu item id.

    The  callback function  must take 2 parameters:
        wiki - Calling PersonalWikiFrame
        evt - wx.CommandEvent

    An  icon descriptor  can be one of the following:
        - a wx.Bitmap object
        - the filename of a bitmap (if file not found, no icon is used)
        - a tuple of filenames, first existing file is used
    """
    
    return (
            (pasteCode, _(u"Paste code")+u"\tCtrl+Shift-V", _(u"Paste source code"), 
                None, None, updateUIElement),
            (addCodeTags, _(u"Add code tags")+u"\tCtrl+Shift-L", _(u"Surround selected source code with the appropriate tags"), 
                None, None, updateUIElement),
            )

def updateUIElement(wiki, evt):
    """
    Update the UI element (menu, toolbar button) according to the context
    @param wiki: the wiki
    @param evt: the event
    """
    if wiki.getCurrentWikiWord() is None:
        evt.Enable(False)
        return
    dpp = wiki.getCurrentDocPagePresenter()
    if dpp is None:
        evt.Enable(False)
        return
    if dpp.getCurrentSubControlName() != "textedit":
        evt.Enable(False)
        return
    evt.Enable(True)     

######################################################################################
# WXHtmlConverter
######################################################################################
WXHtmlConverter = None
def _registerDependentStuff():
    """
    Register all the stuff dependent on libraries not in the original binaries
    This is needed for binary distribution
    """
    import HTMLParser
    class _WXHtmlConverter(HTMLParser.HTMLParser):
        """
        Converts Pygments HTML to a format suitable to wx.HTMLWiget
        """
        def __init__(self):
            HTMLParser.HTMLParser.__init__(self)
            self.out = cStringIO.StringIO()
            self.stack = []
        def handle_starttag(self, tag, attrs):
            if tag.lower() != "span":
                # "normal" tag
                self.out.write("<")
                self.out.write(tag)
                for attr, val in attrs:
                    self.out.write(" ")
                    self.out.write(attr)
                    self.out.write('="')
                    self.out.write(self.encode(val))
                    self.out.write('"')
                self.out.write(">")
                return
            # replace "color=" => "font color="
            # replace "font-weight=" => "b"
            # ...
            stack = []
            for attr, val in attrs:
                self.out.write(" ")
                if attr.lower() == "style":
                    val = val.lower()
                    for spec in val.split(';'):
                        sattr, sval = spec.split(":")
                        sattr = sattr.strip()
                        sval = sval.strip()
                        if sattr == "color":
                            self.out.write('<font color="')
                            self.out.write(self.encode(sval))
                            self.out.write('">')
                            stack.append("</font>")
                        elif sattr == "font-weight":
                            if sval == "bold":
                                self.out.write('<b>')
                                stack.append("</b>")
                        elif sattr == "font-style":
                            if sval == "italic":
                                self.out.write('<i>')
                                stack.append("</i>")
            stack.reverse()
            self.stack.append(stack)
        def handle_endtag(self, tag):
            if tag.lower() != "span":
                # "normal" tag
                self.out.write("</")
                self.out.write(tag)
                self.out.write(">")
                return
            for tag in self.stack.pop():
                self.out.write(tag)
        def handle_charref(self, name):
            self.out.write("&#")
            self.out.write(name)
            self.out.write(";")
        def handle_entityref(self, name):
            self.out.write("&")
            self.out.write(name)
            self.out.write(";")
        def handle_data(self, data):
            self.out.write(data)
        def handle_comment(self, data):
            pass
        def handle_decl(self, decl):
            pass
        def handle_pi(self, data):
            pass
        def encode(self, s):
            s = s.replace("&", "&amp;") # Must be first
            s = s.replace("<", "&lt;")
            s = s.replace(">", "&gt;")
            s = s.replace("'", "&apos;")
            s = s.replace('"', "&quot;")
            return s
    global WXHtmlConverter
    WXHtmlConverter = _WXHtmlConverter

def registerDependentStuff():
    if not WXHtmlConverter:
        _registerDependentStuff()

######################################################################################
# Option dialog
######################################################################################
def registerOptions(ver, app):
    """
    API function for "Options" plugins
    Register configuration options and their GUI presentation
    ver -- API version (can only be 1 currently)
    app -- wxApp object
    """
    import_Pygments(app)
    registerDependentStuff()
    # Register options
    Options.register(app)
    # Register panel in options dialog
    app.addOptionsDlgPanel(OptionsPanel, _(u"Pretty Code"))

try:
    #######################################
    # wxPython 2.8 and later
    #######################################
    from  wx.lib.mixins.listctrl import TextEditMixin, ListCtrlAutoWidthMixin #@UnresolvedImport
except:
    #######################################
    # wxPython 2.4: copy code from 2.8
    #######################################
    from bisect import bisect
    class TextEditMixin:
        """    
        A mixin class that enables any text in any column of a
        multi-column listctrl to be edited by clicking on the given row
        and column.  You close the text editor by hitting the ENTER key or
        clicking somewhere else on the listctrl. You switch to the next
        column by hiting TAB.
    
        To use the mixin you have to include it in the class definition
        and call the __init__ function::
    
            class TestListCtrl(wx.ListCtrl, TextEditMixin):
                def __init__(self, parent, ID, pos=wx.DefaultPosition,
                             size=wx.DefaultSize, style=0):
                    wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
                    TextEditMixin.__init__(self) 
    
    
        Authors:     Steve Zatz, Pim Van Heuven (pim@think-wize.com)
        """
        editorBgColour = wx.Colour(255,255,175) # Yellow
        editorFgColour = wx.Colour(0,0,0)       # black
        def __init__(self):
            #editor = wx.TextCtrl(self, -1, pos=(-1,-1), size=(-1,-1),
            #                     style=wx.TE_PROCESS_ENTER|wx.TE_PROCESS_TAB \
            #                     |wx.TE_RICH2)
    
            self.make_editor()
            self.Bind(wx.EVT_TEXT_ENTER, self.CloseEditor)
            self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
            self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDown)
            self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected)
        def make_editor(self, col_style=wx.LIST_FORMAT_LEFT):
            
            style =wx.TE_PROCESS_ENTER|wx.TE_PROCESS_TAB|wx.TE_RICH2
            style |= {wx.LIST_FORMAT_LEFT: wx.TE_LEFT,
                      wx.LIST_FORMAT_RIGHT: wx.TE_RIGHT,
                      wx.LIST_FORMAT_CENTRE : wx.TE_CENTRE
                      }[col_style]
            editor = wx.TextCtrl(self, -1, style=style)
            editor.SetBackgroundColour(self.editorBgColour)
            editor.SetForegroundColour(self.editorFgColour)
            font = self.GetFont()
            editor.SetFont(font)
    
            self.curRow = 0
            self.curCol = 0
    
            editor.Hide()
            if hasattr(self, 'editor'):
                self.editor.Destroy()
            self.editor = editor
    
            self.col_style = col_style
            self.editor.Bind(wx.EVT_CHAR, self.OnChar)
            self.editor.Bind(wx.EVT_KILL_FOCUS, self.CloseEditor)
        def OnItemSelected(self, evt):
            self.curRow = evt.GetIndex()
            evt.Skip()
        def OnChar(self, event):
            ''' Catch the TAB, Shift-TAB, cursor DOWN/UP key code
                so we can open the editor at the next column (if any).'''
            keycode = event.GetKeyCode()
            if keycode == wx.WXK_TAB and event.ShiftDown():
                self.CloseEditor()
                if self.curCol-1 >= 0:
                    self.OpenEditor(self.curCol-1, self.curRow)
            elif keycode == wx.WXK_TAB:
                self.CloseEditor()
                if self.curCol+1 < self.GetColumnCount():
                    self.OpenEditor(self.curCol+1, self.curRow)
            elif keycode == wx.WXK_ESCAPE:
                self.CloseEditor()
            elif keycode == wx.WXK_DOWN:
                self.CloseEditor()
                if self.curRow+1 < self.GetItemCount():
                    self._SelectIndex(self.curRow+1)
                    self.OpenEditor(self.curCol, self.curRow)
            elif keycode == wx.WXK_UP:
                self.CloseEditor()
                if self.curRow > 0:
                    self._SelectIndex(self.curRow-1)
                    self.OpenEditor(self.curCol, self.curRow)
            else:
                event.Skip()
        def OnLeftDown(self, evt=None):
            ''' Examine the click and double
            click events to see if a row has been click on twice. If so,
            determine the current row and columnn and open the editor.'''
            if self.editor.IsShown():
                self.CloseEditor()
            x,y = evt.GetPosition()
            row,flags = self.HitTest((x,y)) #@UnusedVariable
            if row != self.curRow: # self.curRow keeps track of the current row
                evt.Skip()
                return
            # the following should really be done in the mixin's init but
            # the wx.ListCtrl demo creates the columns after creating the
            # ListCtrl (generally not a good idea) on the other hand,
            # doing this here handles adjustable column widths
            self.col_locs = [0]
            loc = 0
            for n in range(self.GetColumnCount()):
                loc = loc + self.GetColumnWidth(n)
                self.col_locs.append(loc)
            col = bisect(self.col_locs, x+self.GetScrollPos(wx.HORIZONTAL)) - 1
            self.OpenEditor(col, row)
        def OpenEditor(self, col, row):
            ''' Opens an editor at the current position. '''
            # give the derived class a chance to Allow/Veto this edit.
            evt = wx.ListEvent(wx.wxEVT_COMMAND_LIST_BEGIN_LABEL_EDIT, self.GetId())
            evt.m_itemIndex = row
            evt.m_col = col
            item = self.GetItem(row, col)
            evt.m_item.SetId(item.GetId()) 
            evt.m_item.SetColumn(item.GetColumn()) 
            evt.m_item.SetData(item.GetData()) 
            evt.m_item.SetText(item.GetText()) 
            ret = self.GetEventHandler().ProcessEvent(evt)
            if ret and not evt.IsAllowed():
                return   # user code doesn't allow the edit.
            if self.GetColumn(col).m_format != self.col_style:
                self.make_editor(self.GetColumn(col).m_format)
            x0 = self.col_locs[col]
            x1 = self.col_locs[col+1] - x0
            scrolloffset = self.GetScrollPos(wx.HORIZONTAL)
    
            # scroll forward
            if x0+x1-scrolloffset > self.GetSize()[0]:
                if wx.Platform == "__WXMSW__":
                    # don't start scrolling unless we really need to
                    offset = x0+x1-self.GetSize()[0]-scrolloffset
                    # scroll a bit more than what is minimum required
                    # so we don't have to scroll everytime the user presses TAB
                    # which is very tireing to the eye
                    addoffset = self.GetSize()[0]/4
                    # but be careful at the end of the list
                    if addoffset + scrolloffset < self.GetSize()[0]:
                        offset += addoffset
                    self.ScrollList(offset, 0)
                    scrolloffset = self.GetScrollPos(wx.HORIZONTAL)
                else:
                    # Since we can not programmatically scroll the ListCtrl
                    # close the editor so the user can scroll and open the editor
                    # again
                    self.editor.SetValue(self.GetItem(row, col).GetText())
                    self.curRow = row
                    self.curCol = col
                    self.CloseEditor()
                    return
            y0 = self.GetItemRect(row)[1]
            
            editor = self.editor
            editor.SetDimensions(x0-scrolloffset,y0, x1,-1)
            
            editor.SetValue(self.GetItem(row, col).GetText()) 
            editor.Show()
            editor.Raise()
            editor.SetSelection(-1,-1)
            editor.SetFocus()
        
            self.curRow = row
            self.curCol = col
        # FIXME: this function is usually called twice - second time because
        # it is binded to wx.EVT_KILL_FOCUS. Can it be avoided? (MW)
        def CloseEditor(self, evt=None):
            ''' Close the editor and save the new value to the ListCtrl. '''
            if not self.editor.IsShown():
                return
            text = self.editor.GetValue()
            self.editor.Hide()
            self.SetFocus()
            # post wxEVT_COMMAND_LIST_END_LABEL_EDIT
            # Event can be vetoed. It doesn't has SetEditCanceled(), what would 
            # require passing extra argument to CloseEditor() 
            evt = wx.ListEvent(wx.wxEVT_COMMAND_LIST_END_LABEL_EDIT, self.GetId())
            evt.m_itemIndex = self.curRow
            evt.m_col = self.curCol
            item = self.GetItem(self.curRow, self.curCol)
            evt.m_item.SetId(item.GetId()) 
            evt.m_item.SetColumn(item.GetColumn()) 
            evt.m_item.SetData(item.GetData()) 
            evt.m_item.SetText(text) #should be empty string if editor was canceled
            ret = self.GetEventHandler().ProcessEvent(evt)
            if not ret or evt.IsAllowed():
                if self.IsVirtual():
                    # replace by whather you use to populate the virtual ListCtrl
                    # data source
                    self.SetVirtualData(self.curRow, self.curCol, text)
                else:
                    self.SetStringItem(self.curRow, self.curCol, text)
            self.RefreshItem(self.curRow)
        def _SelectIndex(self, row):
            listlen = self.GetItemCount()
            if row < 0 and not listlen:
                return
            if row > (listlen-1):
                row = listlen -1
            self.SetItemState(self.curRow, ~wx.LIST_STATE_SELECTED,
                              wx.LIST_STATE_SELECTED)
            self.EnsureVisible(row)
            self.SetItemState(row, wx.LIST_STATE_SELECTED,
                              wx.LIST_STATE_SELECTED)
    class ListCtrlAutoWidthMixin:
        """ A mix-in class that automatically resizes the last column to take up
            the remaining width of the wx.ListCtrl.
    
            This causes the wx.ListCtrl to automatically take up the full width of
            the list, without either a horizontal scroll bar (unless absolutely
            necessary) or empty space to the right of the last column.
    
            NOTE:    This only works for report-style lists.
    
            WARNING: If you override the EVT_SIZE event in your wx.ListCtrl, make
                     sure you call event.Skip() to ensure that the mixin's
                     _OnResize method is called.
    
            This mix-in class was written by Erik Westra <ewestra@wave.co.nz>
        """
        def __init__(self):
            """ Standard initialiser.
            """
            self._resizeColMinWidth = None
            self._resizeColStyle = "LAST"
            self._resizeCol = 0
            self.Bind(wx.EVT_SIZE, self._onResize)
            self.Bind(wx.EVT_LIST_COL_END_DRAG, self._onResize, self)
        def setResizeColumn(self, col):
            """
            Specify which column that should be autosized.  Pass either
            'LAST' or the column number.  Default is 'LAST'.
            """
            if col == "LAST":
                self._resizeColStyle = "LAST"
            else:
                self._resizeColStyle = "COL"
                self._resizeCol = col
        def resizeLastColumn(self, minWidth):
            """ Resize the last column appropriately.
    
                If the list's columns are too wide to fit within the window, we use
                a horizontal scrollbar.  Otherwise, we expand the right-most column
                to take up the remaining free space in the list.
    
                This method is called automatically when the wx.ListCtrl is resized;
                you can also call it yourself whenever you want the last column to
                be resized appropriately (eg, when adding, removing or resizing
                columns).
    
                'minWidth' is the preferred minimum width for the last column.
            """
            self.resizeColumn(minWidth)
        def resizeColumn(self, minWidth):
            self._resizeColMinWidth = minWidth
            self._doResize()
        # =====================
        # == Private Methods ==
        # =====================
        def _onResize(self, event):
            """ Respond to the wx.ListCtrl being resized.
    
                We automatically resize the last column in the list.
            """
            if 'gtk2' in wx.PlatformInfo:
                self._doResize()
            else:
                wx.CallAfter(self._doResize)
            event.Skip()
        def _doResize(self):
            """ Resize the last column as appropriate.
    
                If the list's columns are too wide to fit within the window, we use
                a horizontal scrollbar.  Otherwise, we expand the right-most column
                to take up the remaining free space in the list.
    
                We remember the current size of the last column, before resizing,
                as the preferred minimum width if we haven't previously been given
                or calculated a minimum width.  This ensure that repeated calls to
                _doResize() don't cause the last column to size itself too large.
            """
            if not self:  # avoid a PyDeadObject error
                return
            if self.GetSize().height < 32:
                return  # avoid an endless update bug when the height is small.
            numCols = self.GetColumnCount()
            if numCols == 0: return # Nothing to resize.
    
            if(self._resizeColStyle == "LAST"):
                resizeCol = self.GetColumnCount()
            else:
                resizeCol = self._resizeCol
    
            resizeCol = max(1, resizeCol)
    
            if self._resizeColMinWidth == None:
                self._resizeColMinWidth = self.GetColumnWidth(resizeCol - 1)
            # We're showing the vertical scrollbar -> allow for scrollbar width
            # NOTE: on GTK, the scrollbar is included in the client size, but on
            # Windows it is not included
            listWidth = self.GetClientSize().width
            if wx.Platform != '__WXMSW__':
                if self.GetItemCount() > self.GetCountPerPage():
                    scrollWidth = wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
                    listWidth = listWidth - scrollWidth
    
            totColWidth = 0 # Width of all columns except last one.
            for col in range(numCols):
                if col != (resizeCol-1):
                    totColWidth = totColWidth + self.GetColumnWidth(col)
    
            if totColWidth + self._resizeColMinWidth > listWidth:
                # We haven't got the width to show the last column at its minimum
                # width -> set it to its minimum width and allow the horizontal
                # scrollbar to show.
                self.SetColumnWidth(resizeCol-1, self._resizeColMinWidth)
                return
            # Resize the last column to take up the remaining available space.
            self.SetColumnWidth(resizeCol-1, listWidth - totColWidth)

class DictEdit(wx.ListCtrl,
                   ListCtrlAutoWidthMixin,
                   TextEditMixin):
    """"
    A simple listCtrl which allows to edit dictionaries = list of (key, value)
    """
    def __init__(self, parent, ID, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0, choices={}, listChoices = None):
        """
        Constructor
        """
        wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
        ListCtrlAutoWidthMixin.__init__(self)
        TextEditMixin.__init__(self)
        self.listChoices = listChoices
        self.Populate(choices)
    def Populate(self, choices):
        """
        Populate the list
        """
        self.InsertColumn(0, _(u"Name"))
        self.InsertColumn(1, _(u"Style"))
        self.SetColumnWidth(0, 100)
        self.SetColumnWidth(1, wx.LIST_AUTOSIZE)
        for k, v in choices.iteritems():
            index = self.InsertStringItem(sys.maxint, k)
            self.SetStringItem(index, 1, v)
    def AddNewItem(self, name_tmpl, value):
        """
        Add the new item such as the key is unique
        """
        i = 1
        while True:
            k = name_tmpl % i
            if self.FindItem(-1, k) < 0:
                break
            i += 1
        index = self.InsertStringItem(sys.maxint, k)
        self.SetStringItem(index, 1, value)
        if self.listChoices:
            self.listChoices.Append(k)
    def DelSelection(self):
        """
        Delete the selected rows
        """
        res = []
        while self.GetSelectedItemCount() != 0:
            if self.listChoices:
                text = self.GetItemText(self.GetFirstSelected())
                i = self.listChoices.FindString(text)
                if i >= 0:
                    self.listChoices.Delete(i)
                    if self.listChoices.GetSelection() <= 0:
                        self.listChoices.SetStringSelection(NO_BKG)
            self.DeleteItem(self.GetFirstSelected())
        return res
    def SetStringItem(self, index, col, data):
        """
        Edit the text of an item. Duplicate or empty keys are not allowed.
        """
        data = data.strip()
        if (col == 0):
            if  ((not data) or (self.FindItem(-1, data) >= 0) or (data == NO_BKG)):
                return
            if self.listChoices:
                i = self.listChoices.FindString(self.GetItemText(index))
                sel = (i == self.listChoices.GetSelection())
                self.listChoices.SetString(i, data)
                if sel: self.listChoices.SetSelection(i)
        wx.ListCtrl.SetStringItem(self, index, col, data)

class OptionsPanel(wx.Panel):
    """
    The option panel for the plugin
    """
    def __init__(self, parent, optionsDlg, app):
        """
        Constructor
        """
        global pygments
        import_Pygments(app)
        registerDependentStuff()
        from .pygments.lexers import get_all_lexers #@UnresolvedImport
        #
        wx.Panel.__init__(self, parent)
        self.app = app
        #
        self.options = Options(self.app.getGlobalConfig())
        #
        langs = [unicode(lang_def[0], "utf-8", "ignore") for lang_def in get_all_lexers()]
        langs.sort()
        #
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        #
        box = wx.StaticBox(self, -1, _("Default options"))
        boxSizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        gridSizer = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
        lLang = wx.StaticText(self, -1, _("Language:"))
        self.lang = wx.Choice(self, -1, choices = langs)
        if not self.lang.SetStringSelection(self.options.lang):
            self.lang.SetStringSelection(DEFAULT_LANG)
        lBkg = wx.StaticText(self, -1, _("Background:"))
        self.bkg = wx.Choice(self, -1, choices = [NO_BKG] + self.options.bkgs.keys())
        if not self.bkg.SetStringSelection(self.options.bkg):
            self.bkg.SetSelection(0)
        self.lineNb = wx.CheckBox(self, -1, _("Show line numbers"))
        self.lineNb.SetValue(self.options.showLN)
        gridSizer.Add(lLang, 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self.lang, 0, wx.EXPAND)
        gridSizer.Add(lBkg, 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
        gridSizer.Add(self.bkg, 0, wx.EXPAND)
        gridSizer.Add((10, 10))
        gridSizer.Add(self.lineNb, 0, wx.EXPAND)
        boxSizer.Add(gridSizer, -1, wx.ALL|wx.EXPAND, 5)
        mainSizer.Add(boxSizer, 0, wx.ALL|wx.EXPAND, 5)
        #
        box = wx.StaticBox(self, -1, _("Backgrounds"))
        boxSizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        gridSizer = wx.BoxSizer(wx.HORIZONTAL)
        addBkg = wx.BitmapButton(self, -1, wx.ArtProvider.GetBitmap(wx.ART_NEW))
        self.Bind(wx.EVT_BUTTON, self.OnAddBkg, addBkg)
        delBkg = wx.BitmapButton(self, -1, wx.ArtProvider.GetBitmap(wx.ART_DELETE))
        self.Bind(wx.EVT_BUTTON, self.OnDelBkg, delBkg)
        gridSizer.Add((10, 10), 1, flag=wx.EXPAND)
        gridSizer.Add(addBkg, 0, flag=wx.EXPAND)
        gridSizer.Add(delBkg, 0, flag=wx.EXPAND)
        self.lBkgs = DictEdit(self, wx.NewId(), 
            choices = self.options.bkgs, listChoices = self.bkg, style=wx.LC_REPORT|wx.BORDER_NONE|wx.LC_SORT_ASCENDING)
        boxSizer.Add(gridSizer, 0, wx.EXPAND, 5)
        boxSizer.Add(self.lBkgs, 1, wx.ALL|wx.EXPAND, 5)
        mainSizer.Add(boxSizer, 1, wx.ALL|wx.EXPAND, 5)
        #
        self.SetSizer(mainSizer)
        self.Fit()
    def OnAddBkg(self, event):
        self.lBkgs.AddNewItem(BKG_NEW, BKG_TMPL)
    def OnDelBkg(self, event):
        self.lBkgs.DelSelection()
    def setVisible(self, vis):
        """
        Called when panel is shown or hidden. The actual wxWindow.Show()
        function is called automatically.
        
        If a panel is visible and becomes invisible because another panel is
        selected, the plugin can veto by returning False.
        When becoming visible, the return value is ignored.
        """
        return True
    def checkOk(self):
        """
        Called when "OK" is pressed in dialog. The plugin should check here if
        all input values are valid. If not, it should return False, then the
        Options dialog automatically shows this panel.
        
        There should be a visual indication about what is wrong (e.g. red
        background in text field). Be sure to reset the visual indication
        if field is valid again.
        """
        return True
    def handleOk(self):
        """
        This is called if checkOk() returned True for all panels. Transfer here
        all values from text fields, checkboxes, ... into the configuration
        file.
        """
        self.options.lang = self.lang.GetStringSelection()
        self.options.bkg = self.bkg.GetStringSelection()
        self.options.showLN = self.lineNb.GetValue()
        self.options.bkgs = {}
        for i in xrange(self.lBkgs.GetItemCount()):
            self.options.bkgs[self.lBkgs.GetItemText(i).strip()] = self.lBkgs.GetItem(i, 1).GetText().strip()
        self.options.save()

######################################################################################
# Insertion
######################################################################################
def describeInsertionKeys(ver, app):
    """
    API function for "InsertionByKey" plugins
    Returns a sequence of tuples describing the supported
    insertion keys. Each tuple has the form (insKey, exportTypes, handlerFactory)
    where insKey is the insertion key handled, exportTypes is a sequence of
    strings describing the supported export types and handlerFactory is
    a factory function (normally a class) taking the wxApp object as
    parameter and returning a handler object fulfilling the protocol
    for "insertion by key" (see EqnHandler as example).
    
    This plugin uses the special export type "wikidpad_language" which is
    not a real type like HTML export, but allows to return a string
    which conforms to WikidPad wiki syntax and is postprocessed before
    exporting.
    Therefore this plugin is not bound to a specific export type.

    ver -- API version (can only be 1 currently)
    app -- wxApp object
    """
    return (
            (INSERTION_TAG, ("html_single", "html_previewWX", "html_preview", "html_multi"), InsertionHandler),
            )

class InsertionHandler(object):
    def __init__(self, app):
        """
        Constructor
        """
        self.app = app
    def taskStart(self, exporter, exportType):
        """
        This is called before any call to createContent() during an
        export task.
        An export task can be a single HTML page for
        preview or a single page or a set of pages for export.
        exporter -- Exporter object calling the handler
        exportType -- string describing the export type
        
        Calls to createContent() will only happen after a 
        call to taskStart() and before the call to taskEnd()
        """
        pass
    def taskEnd(self):
        """
        Called after export task ended and after the last call to
        createContent().
        """
        pass
    def createContent(self, exporter, exportType, insToken):
        """
        Handle an insertion and create the appropriate content.

        exporter -- Exporter object calling the handler
        exportType -- string describing the export type
        insToken -- insertion token to create content for (see also 
                PageAst.Insertion)

        An insertion token has the following member variables:
            key: insertion key (unistring)
            value: value of an insertion (unistring)
            appendices: sequence of strings with the appendices

        Meaning and type of return value is solely defined by the type
        of the calling exporter.
        
        For HtmlXmlExporter a unistring is returned with the HTML code
        to insert instead of the insertion.        
        """
        options = Options(self.app.getGlobalConfig())
        optionFound = False

        def handleOption(name, value):
            name = name.strip().lower()
            value = value.strip()

            if name == u"lang":
                options.lang = value
            elif name == u"showlines":
                options.showLN = int(value) != 0
            elif name == u"startline":
                options.startLine = int(value)
            elif name == u"hllines":
                if value:
                    options.hlLines = [int(x) for x in value.split(",")]
                else:
                    options.hlLines = []
            elif name == u"bkg":
                if value != u"default":
                    options.bkg = value
            else:
                raise Exception("invalid option name: '%s'" % name)


        try:
            code, soptions = insToken.value.rsplit(u":::", 1)
            soptionArgs = soptions.split(u";")
        except ValueError:
            code = insToken.value
            soptionArgs = []

        try:
            for setopt in soptionArgs:
                try:
                    name, value = setopt.split(u"=", 1)
                except ValueError:
                    name, value = setopt.split(u":", 1)
                    
                handleOption(name, value)
                optionFound = True

            for setopt in insToken.appendices:
                try:
                    name, value = setopt.split(u"=", 1)
                except ValueError:
                    name, value = setopt.split(u":", 1)
                
                handleOption(name, value)
                optionFound = True
            
        except Exception, e:
            return  \
                u"<span style='color: #CC033C'>" \
                u"prettyCode: <b>Invalid option format. (%s)</b> Use 'lang=C++;showLine=0;...'" \
                u"</span>" % (str(e))        

        if not optionFound:
            return \
                u"<span style='color: #CC033C'>" \
                u"prettyCode: <b>Invalid format.</b> Use [:%s:///source code:::lang=C++;showLine=0;...///]" \
                u"</span>" % INSERTION_TAG



        import_Pygments(self.app)
        registerDependentStuff()
        from .pygments import highlight #@UnresolvedImport
        from .pygments.lexers import get_lexer_by_name #@UnresolvedImport
        from .pygments.formatters import HtmlFormatter #@UnresolvedImport
        
        try:
            lexer = get_lexer_by_name(options.lang.encode("utf-8", "ignore").lower(), stripall=True, encoding = None)
        except:
            return  \
                u"<span style='color: #CC033C'>" \
                u"prettyCode: <b>Invalid language name '%s'" \
                u"</span>" % (options.lang)
        if options.showLN:
            showLN = "inline"
        else:
            showLN = False  
        formatter = HtmlFormatter(
            cssclass="source", noclasses = True, encoding = None,
            linenos=showLN, linenostart = options.startLine, hl_lines = options.hlLines,
            )
        result = highlight(code, lexer, formatter)
        bkgs = dict(zip([x.lower() for x in options.bkgs.keys()], options.bkgs.values()))
        bkg = bkgs.get(options.bkg.lower(), "").replace("'", '"')
        if bkg:
            result = '<pre style="%s">%s</pre>' % (bkg, result)
        html = result.encode("utf8", 'replace')
        if exportType == "html_previewWX":
            # we need to convert the HTML spans to font, b, i, ..
            parser = WXHtmlConverter()
            parser.feed(html)
            parser.close()
            result = unicode(parser.out.getvalue(), 'utf8', 'replace')
        return result

    def getExtraFeatures(self):
        """
        Returns a list of bytestrings describing additional features supported
        by the plugin. Currently not specified further.
        """
        return ()

######################################################################################
# src highlighting
######################################################################################
def insertCode(wiki, text, replace=False):
    """
    Insert some code into the wiki
    @param wiki: the wiki
    @param text: the text to insert
    """
    # Get the clipboard contents ?
    options = Options(wiki.getConfig())
    text = u"[:%s:///\n" % INSERTION_TAG + text
    if not text.endswith("\n"):
        text += "\n"
    text += u":::lang=%s;showLines=%d;startLine=%d;hlLines=%s;Bkg=default///]\n" % \
        (
         options.lang, 
         int(options.showLN), 
         options.startLine, 
         ",".join([str(x)for x in options.hlLines],
        ))
    if replace:
        wiki.getActiveEditor().ReplaceSelection(text)
    else:
        wiki.getActiveEditor().AddText(text)

def pasteCode(wiki, evt):
    """
    Paste the contents of the clipboard as code
    @param wiki: the wiki
    @param evt: the triggering event
    """
    # Get the clipboard contents ?
    text = u""
    data = wx.TextDataObject()
    if wx.TheClipboard.Open():
        success = wx.TheClipboard.GetData(data)
        wx.TheClipboard.Close()
        if success:
            text += data.GetText()
    insertCode(wiki, text)

def addCodeTags(wiki, evt):
    """
    Add the plugin tags to the current selection
    @param wiki: the wiki
    @param evt: the triggering event
    """
    text = wiki.getActiveEditor().GetSelectedText()
    insertCode(wiki, text, True)

######################################################################################
