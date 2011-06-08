import time
import logging

import apt
import apt_pkg
import gobject
from gi.repository import Gtk, Pango

from ubuntutweak.gui import GuiBuilder
from ubuntutweak.utils import icon
from ubuntutweak.modules import ModuleLoader
from ubuntutweak.settings import GSetting

log = logging.getLogger('Janitor')

class CruftObject(object):
    def __init__(self, name, path=None, size=None):
        self.name = name
        self.path = path
        self.size = size

    def get_name(self):
        return self.name

    def get_size(self):
        return None

    def get_icon(self):
        return None


class JanitorPlugin(object):
    __title__ = ''
    __category__ = ''
    __utmodule__ = ''
    __utactive__ = True

    cache = None

    @classmethod
    def get_name(cls):
        return cls.__name__

    @classmethod
    def get_title(cls):
        return cls.__title__

    @classmethod
    def get_category(cls):
        return cls.__category__

    def get_cruft(self):
        return ()

    def get_cache(self):
        try:
            self.update_apt_cache()
        except Exception, e:
            self.is_apt_broken = True
            self.apt_broken_message = e
            log.error("Error happened when get_cache(): %s" % str(e))
            return None
        else:
            return self.cache

    def update_apt_cache(self, init=False):
        '''if init is true, force to update, or it will update only once'''
        if init or not getattr(self, 'cache'):
            apt_pkg.init()
            self.cache = apt.Cache()


class JanitorPage(Gtk.VBox, GuiBuilder):
    (JANITOR_CHECK,
     JANITOR_ICON,
     JANITOR_NAME,
     JANITOR_PLUGIN,
     JANITOR_SPINNER_ACTIVE,
     JANITOR_SPINNER_PULSE) = range(6)

    (RESULT_CHECK,
     RESULT_ICON,
     RESULT_NAME,
     RESULT_DESC) = range(4)

    max_janitor_view_width = 0

    def __init__(self):
        gobject.GObject.__init__(self)
        self.set_border_width(6)
        GuiBuilder.__init__(self, 'janitorpage.ui')

        self.loader = ModuleLoader('janitor')
        self.autoscan_setting = GSetting('com.ubuntu-tweak.tweak.auto-scan')

        self.pack_start(self.vbox1, True, True, 0)

        self.connect('realize', self.setup_ui_tasks)
        self.janitor_view.get_selection().connect('changed', self.on_janitor_selection_changed)
        self.show()

    def is_auto_scan(self):
        return self.autoscan_button.get_active()

    def setup_ui_tasks(self, widget):
        #add janitor columns
        janitor_column = Gtk.TreeViewColumn()

        renderer = Gtk.CellRendererToggle()
        renderer.connect('toggled', self.on_janitor_check_button_toggled)
        janitor_column.pack_start(renderer, False)
        janitor_column.add_attribute(renderer, 'active', self.JANITOR_CHECK)

        self.janitor_view.append_column(janitor_column)

        janitor_column = Gtk.TreeViewColumn()

        renderer = Gtk.CellRendererPixbuf()
        janitor_column.pack_start(renderer, False)
        janitor_column.add_attribute(renderer, 'pixbuf', self.JANITOR_ICON)
        janitor_column.set_cell_data_func(renderer,
                                          self.icon_column_view_func,
                                          self.JANITOR_ICON)

        renderer = Gtk.CellRendererText()
        renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        janitor_column.pack_start(renderer, True)
        janitor_column.add_attribute(renderer, 'text', self.JANITOR_NAME)

        renderer = Gtk.CellRendererSpinner()
        janitor_column.pack_start(renderer, False)
        janitor_column.add_attribute(renderer, 'active', self.JANITOR_SPINNER_ACTIVE)
        janitor_column.add_attribute(renderer, 'pulse', self.JANITOR_SPINNER_PULSE)

        self.janitor_view.append_column(janitor_column)
        #end janitor columns

        #add result columns
        result_column = Gtk.TreeViewColumn()

        renderer = Gtk.CellRendererToggle()
        renderer.connect('toggled', self.on_result_check_renderer_toggled)
        result_column.pack_start(renderer, False)
        result_column.add_attribute(renderer, 'active', self.RESULT_CHECK)

        renderer = Gtk.CellRendererPixbuf()
        result_column.pack_start(renderer, False)
        result_column.add_attribute(renderer, 'pixbuf', self.RESULT_ICON)
        result_column.set_cell_data_func(renderer,
                                         self.icon_column_view_func,
                                         self.RESULT_ICON)

        renderer = Gtk.CellRendererText()
        renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        result_column.pack_start(renderer, True)
        result_column.add_attribute(renderer, 'text', self.RESULT_NAME)

        renderer = Gtk.CellRendererText()
        result_column.pack_start(renderer, False)
        result_column.add_attribute(renderer, 'text', self.RESULT_DESC)

        self.result_view.append_column(result_column)
        #end result columns

        auto_scan = self.autoscan_setting.get_value()
        log.info("Auto scan status: %s", auto_scan)

        self.scan_button.set_visible(not auto_scan)
        self.autoscan_button.set_active(auto_scan)

        self.update_model()
        self.janitor_view.expand_all()
        if self.max_janitor_view_width:
            self.janitor_view.set_size_request(self.max_janitor_view_width, -1)

    def on_janitor_selection_changed(self, selection):
        model, iter = selection.get_selected()
        if iter and not self.janitor_model.iter_has_child(iter):
            plugin = model[iter][self.JANITOR_PLUGIN]

            plugin_iter = self.result_model.get_iter_first()
            for row in self.result_model:
                if row[self.RESULT_NAME] == plugin.get_title():
                    self.result_view.get_selection().select_path(row.path)
                    self.result_view.scroll_to_cell(row.path)

    def on_janitor_check_button_toggled(self, cell, path):
        iter = self.janitor_model.get_iter(path)
        checked = self.janitor_model[iter][self.JANITOR_CHECK]

        if self.janitor_model.iter_has_child(iter):
            child_iter = self.janitor_model.iter_children(iter)
            while child_iter:
                self.janitor_model[child_iter][self.JANITOR_CHECK] = not checked

                child_iter = self.janitor_model.iter_next(child_iter)

        self.janitor_model[iter][self.JANITOR_CHECK] = not checked

        self.check_child_is_all_the_same(self.janitor_model, iter,
                                         self.JANITOR_CHECK, not checked)

        if self.is_auto_scan():
            self.scan_cruft(iter, not checked)

    def on_result_check_renderer_toggled(self, cell, path):
        iter = self.result_model.get_iter(path)
        checked = self.result_model[iter][self.RESULT_CHECK]

        if self.result_model.iter_has_child(iter):
            child_iter = self.result_model.iter_children(iter)
            while child_iter:
                self.result_model[child_iter][self.RESULT_CHECK] = not checked

                child_iter = self.result_model.iter_next(child_iter)

        self.result_model[iter][self.RESULT_CHECK] = not checked

        self.check_child_is_all_the_same(self.result_model, iter,
                                         self.RESULT_CHECK, not checked)

    def check_child_is_all_the_same(self, model, iter, column_id, status):
        iter = model.iter_parent(iter)

        if iter:
            child_iter = model.iter_children(iter)

            while child_iter:
                if status != model[child_iter][column_id]:
                    model[iter][column_id] = False
                    break
                child_iter = model.iter_next(child_iter)
            else:
                model[iter][column_id] = status

    def scan_cruft(self, iter, checked):
        if self.janitor_model.iter_has_child(iter):
            log.info('Scan cruft for all plugins')
            #Scan cruft for children
            child_iter = self.janitor_model.iter_children(iter)
            self.result_model.clear()
            while child_iter:
                self.do_plugin_scan(child_iter, checked)
                child_iter = self.janitor_model.iter_next(child_iter)
        else:
            self.do_plugin_scan(iter, checked)

    def do_plugin_scan(self, plugin_iter, checked):
        #Scan cruft for current iter
        plugin = self.janitor_model[plugin_iter][self.JANITOR_PLUGIN]
        log.info('Scan cruft for plugin: %s' % plugin.get_name())
        if checked:
            iter = self.result_model.append(None, (None,
                                                   None,
                                                   plugin.get_title(),
                                                   None))

            self.janitor_model[plugin_iter][self.JANITOR_SPINNER_ACTIVE] = True
            for i, cruft in enumerate(plugin.get_cruft()):
                while Gtk.events_pending():
                    Gtk.main_iteration()

                self.janitor_model[plugin_iter][self.JANITOR_SPINNER_PULSE] = i
                self.result_model.append(iter, (False,
                                                cruft.get_icon(),
                                                cruft.get_name(),
                                                cruft.get_size()))
            self.janitor_model[plugin_iter][self.JANITOR_SPINNER_ACTIVE] = False

            self.result_view.expand_all()
        else:
            iter = self.result_model.get_iter_first()
            for row in self.result_model:
                if row[self.RESULT_NAME] == plugin.get_title():
                    self.result_model.remove(iter)

    def on_clean_button_clicked(self, widget):
        iter = self.result_model.get_iter_first()

        if iter:
            child_iter = self.result_model.iter_children(iter)
            while child_iter:
                self.result_model.get_value(child_iter, self.JANITOR_CHECK)

                child_iter = self.janitor_model.iter_next(child_iter)

    def on_autoscan_button_toggled(self, widget):
        if widget.get_active():
            self.autoscan_setting.set_value(True)
            self.scan_button.hide()
        else:
            self.autoscan_setting.set_value(False)
            self.scan_button.show()

    def icon_column_view_func(self, cell_layout, renderer, model, iter, id):
        if model[iter][id] == None:
            renderer.set_property("visible", False)
        else:
            renderer.set_property("visible", True)

    def update_model(self):
        size_list = []

        iter = self.janitor_model.append(None, (None,
                                                icon.get_from_name('ubuntu-logo', size=32),
                                                _('System'),
                                                None,
                                                None,
                                                None))

        for plugin in self.loader.get_modules_by_category('system'):
            size_list.append(Gtk.Label(plugin.get_title()).get_layout().get_pixel_size()[0])
            self.janitor_model.append(iter, (False,
                                             None,
                                             plugin.get_title(),
                                             plugin(),
                                             None,
                                             None))

        iter = self.janitor_model.append(None, (None,
                                                icon.get_from_name('system-users', size=32),
                                                _('Personal'),
                                                None,
                                                None,
                                                None))

        for plugin in self.loader.get_modules_by_category('personal'):
            size_list.append(Gtk.Label(plugin.get_title()).get_layout().get_pixel_size()[0])
            self.janitor_model.append(iter, (False,
                                             None,
                                             plugin.get_title(),
                                             plugin(),
                                             None,
                                             None))
        if size_list:
            self.max_janitor_view_width = max(size_list) + 60