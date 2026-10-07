"""Small StatusNotifierItem with an Ayatana text label for Ubuntu's top panel."""

import os

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib


ITEM_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionMovieName" type="s" access="read"/>
    <property name="XAyatanaLabel" type="s" access="read"/>
    <property name="XAyatanaLabelGuide" type="s" access="read"/>
    <property name="IconAccessibleDesc" type="s" access="read"/>
    <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
    <signal name="XAyatanaNewLabel"><arg type="s"/><arg type="s"/></signal>
  </interface>
</node>
"""

MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" direction="in"/><arg type="i" direction="in"/>
      <arg type="as" direction="in"/><arg type="u" direction="out"/>
      <arg type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" direction="in"/><arg type="as" direction="in"/>
      <arg type="a(ia{sv})" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" direction="in"/><arg type="s" direction="in"/>
      <arg type="v" direction="in"/><arg type="u" direction="in"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" direction="in"/><arg type="b" direction="out"/>
    </method>
  </interface>
</node>
"""


class PanelIndicator:
    def __init__(self, on_activate, actions=None):
        self.on_activate = on_activate
        self.actions = actions or {}
        self.phase = "idle"
        self.paused = False
        self.label = "25:00"
        self.bus_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.info = Gio.DBusNodeInfo.new_for_xml(ITEM_XML).interfaces[0]
        self.registration = self.bus.register_object(
            "/StatusNotifierItem", self.info, self._method_call, self._get_property, None
        )
        self.menu_info = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]
        self.menu_registration = self.bus.register_object(
            "/MenuBar", self.menu_info, self._menu_call, self._menu_property, None
        )
        self.bus.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus",
            "org.freedesktop.DBus", "RequestName",
            GLib.Variant("(su)", (self.bus_name, 0)), None,
            Gio.DBusCallFlags.NONE, 2000, None,
        )
        self.bus.call(
            "org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher",
            "org.kde.StatusNotifierWatcher", "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (self.bus_name,)), None,
            Gio.DBusCallFlags.NONE, 5000, None, self._registered, None,
        )

    def _registered(self, connection, result, _user_data):
        try:
            connection.call_finish(result)
        except GLib.Error as error:
            print(f"Panel indikatorini ro‘yxatga olishda xato: {error}")

    def _get_property(self, _bus, _sender, _path, _interface, property_name):
        values = {
            "Category": ("s", "ApplicationStatus"),
            "Id": ("s", "pomodoro-ubuntu"),
            "Title": ("s", "Pomodoro Ubuntu"),
            "Status": ("s", "Active"),
            "WindowId": ("i", 0),
            "IconThemePath": ("s", ""),
            "Menu": ("o", "/MenuBar"),
            "ItemIsMenu": ("b", False),
            "IconName": ("s", "alarm-symbolic"),
            "IconPixmap": ("a(iiay)", []),
            "OverlayIconName": ("s", ""),
            "OverlayIconPixmap": ("a(iiay)", []),
            "AttentionIconName": ("s", ""),
            "AttentionIconPixmap": ("a(iiay)", []),
            "AttentionMovieName": ("s", ""),
            "XAyatanaLabel": ("s", self.label),
            "XAyatanaLabelGuide": ("s", "888:88"),
            "IconAccessibleDesc": ("s", f"Pomodoro {self.label}"),
        }
        signature, value = values[property_name]
        return GLib.Variant(signature, value)

    def _method_call(self, _bus, _sender, _path, _interface, method, _parameters, invocation):
        if method in ("Activate", "ContextMenu", "SecondaryActivate"):
            self.on_activate()
        invocation.return_value(None)

    def _menu_property(self, _bus, _sender, _path, _interface, name):
        values = {
            "Version": ("u", 3),
            "TextDirection": ("s", "ltr"),
            "Status": ("s", "normal"),
            "IconThemePath": ("as", []),
        }
        signature, value = values[name]
        return GLib.Variant(signature, value)

    def _menu_call(self, _bus, _sender, _path, _interface, method, parameters, invocation):
        if method == "GetLayout":
            children = [GLib.Variant("(ia{sv}av)", (item_id, props, []))
                        for item_id, props in self._menu_items().items()]
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (1, (0, {}, children))))
        elif method == "GetGroupProperties":
            requested = parameters.unpack()[0]
            items = self._menu_items()
            properties = [(item_id, items[item_id]) for item_id in requested if item_id in items]
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (properties,)))
        elif method == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (True,)))
        elif method == "Event":
            item_id, event, _data, _timestamp = parameters.unpack()
            if event == "clicked":
                callbacks = {1: self.on_activate, 2: self.actions.get("primary"),
                             3: self.actions.get("skip"), 4: self.actions.get("stop")}
                callback = callbacks.get(item_id)
                if callback:
                    callback()
            invocation.return_value(None)

    def _menu_items(self):
        def props(label):
            return {"label": GLib.Variant("s", label)}

        items = {1: props("Pomodoro oynasini ochish")}
        if self.phase == "idle":
            items[2] = props("Boshlash")
        else:
            items[2] = props("Davom ettirish" if self.paused else "Pauza")
            if self.phase == "break":
                items[3] = props("Tanaffusni o‘tkazish")
            items[4] = props("To‘xtatish")
        return items

    def set_phase(self, phase, paused):
        self.phase = phase
        self.paused = paused

    def close(self):
        self.bus.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus",
            "org.freedesktop.DBus", "ReleaseName",
            GLib.Variant("(s)", (self.bus_name,)), None,
            Gio.DBusCallFlags.NONE, 2000, None,
        )
        self.bus.unregister_object(self.menu_registration)
        self.bus.unregister_object(self.registration)

    def set_label(self, label):
        if self.label == label:
            return
        self.label = label
        self.bus.emit_signal(
            None, "/StatusNotifierItem", "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            GLib.Variant("(sa{sv}as)", (
                "org.kde.StatusNotifierItem",
                {"XAyatanaLabel": GLib.Variant("s", label),
                 "IconAccessibleDesc": GLib.Variant("s", f"Pomodoro {label}")},
                [],
            )),
        )
        self.bus.emit_signal(
            None, "/StatusNotifierItem", "org.kde.StatusNotifierItem",
            "XAyatanaNewLabel", GLib.Variant("(ss)", (label, "888:88")),
        )
