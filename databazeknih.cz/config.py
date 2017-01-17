#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Pavel Skulil <pavelsku@gmail.com>'
__docformat__ = 'restructuredtext cs'

try:
    from PyQt5 import Qt as QtGui
    from PyQt5.Qt import QLabel, QHBoxLayout, Qt, QGroupBox
except ImportError:
    from PyQt4 import QtGui
    from PyQt4.Qt import QLabel, QHBoxLayout, Qt, QGroupBox
from calibre.gui2.metadata.config import ConfigWidget as DefaultConfigWidget
from calibre.utils.config import JSONConfig

STORE_NAME = 'Options'
KEY_MAX_DOWNLOADS = 'maxDownloads'

DEFAULT_STORE_VALUES = {
    KEY_MAX_DOWNLOADS: 10
}

# This is where all preferences for this plugin will be stored
plugin_prefs = JSONConfig('plugins/databazeknih')

# Set defaults
plugin_prefs.defaults[STORE_NAME] = DEFAULT_STORE_VALUES


class ConfigWidget(DefaultConfigWidget):

    def __init__(self, plugin):
        DefaultConfigWidget.__init__(self, plugin)
        c = plugin_prefs[STORE_NAME]

        other_group_box = QGroupBox('Other options', self)
        self.l.addWidget(other_group_box, self.l.rowCount(), 0, 1, 2)
        other_group_box_layout = QHBoxLayout()
        other_group_box.setLayout(other_group_box_layout)

        max_label = QLabel('Maximum title/author search matches to evaluate (1 = fastest):', self)
        max_label.setToolTip('Libri.hu do not always have links to large covers for every ISBN\n'
                             'of the same book. Increasing this value will take effect when doing\n'
                             'title/author searches to consider more ISBN editions.\n\n'
                             'This will increase the potential likelihood of getting a larger cover\n'
                             'though does not guarantee it.')
        other_group_box_layout.addWidget(max_label)
        self.max_downloads_spin = QtGui.QSpinBox(self)
        self.max_downloads_spin.setMinimum(5)
        self.max_downloads_spin.setMaximum(50)
        self.max_downloads_spin.setProperty('value', c.get(KEY_MAX_DOWNLOADS, DEFAULT_STORE_VALUES[KEY_MAX_DOWNLOADS]))
        other_group_box_layout.addWidget(self.max_downloads_spin)
        other_group_box_layout.insertStretch(-1)

    def commit(self):
        DefaultConfigWidget.commit(self)
        new_prefs = {}
        new_prefs[KEY_MAX_DOWNLOADS] = int(unicode(self.max_downloads_spin.value()))
        plugin_prefs[STORE_NAME] = new_prefs

