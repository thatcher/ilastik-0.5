#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    Copyright 2010 C Sommer, C Straehle, U Koethe, FA Hamprecht. All rights reserved.
#    
#    Redistribution and use in source and binary forms, with or without modification, are
#    permitted provided that the following conditions are met:
#    
#       1. Redistributions of source code must retain the above copyright notice, this list of
#          conditions and the following disclaimer.
#    
#       2. Redistributions in binary form must reproduce the above copyright notice, this list
#          of conditions and the following disclaimer in the documentation and/or other materials
#          provided with the distribution.
#    
#    THIS SOFTWARE IS PROVIDED BY THE ABOVE COPYRIGHT HOLDERS ``AS IS'' AND ANY EXPRESS OR IMPLIED
#    WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
#    FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE ABOVE COPYRIGHT HOLDERS OR
#    CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
#    CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#    SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
#    ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
#    NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
#    ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#    
#    The views and conclusions contained in the software and documentation are those of the
#    authors and should not be interpreted as representing official policies, either expressed
#    or implied, of their employers.

import os
import ilastik

class ilastikIcons(object):
    #get the absolute path of the 'ilastik' module
    ilastikPath = os.path.dirname(ilastik.__file__)
    
    iconPath = ilastikPath+'/gui/icons/32x32/'
    Brush = iconPath + 'actions/edit-clear.png'
    Play = iconPath + "actions/media-playback-start.png"
    View = iconPath + 'emotes/face-glasses.png'
    Segment = iconPath + "actions/my-segment.png" 
    Undo = iconPath + 'actions/edit-undo.png'
    Redo = iconPath + 'actions/edit-redo.png'
    DoubleArrow = iconPath + 'actions/media-seek-forward.png'
    Preferences = iconPath + 'categories/preferences-system.png'
    New = iconPath + "actions/document-new.png" 
    Open = iconPath + "actions/document-open.png" 
    Save = iconPath + "actions/document-save.png" 
    Edit = iconPath + "actions/document-properties.png" 
    System = iconPath + "categories/applications-system.png"
    Dialog = iconPath + "status/dialog-information.png"
    Select = iconPath + "actions/edit-select-all.png"
    Erase = iconPath + "actions/my_erase.png"
    Edit2 = iconPath + "actions/edit-find-replace.png"
    Python = iconPath + ilastikPath+"/gui/pyc.ico"
    
    
    