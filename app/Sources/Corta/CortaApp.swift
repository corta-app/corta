import AppKit
import PiezaCatalogo

/// Corta para Mac: una ventana con la interfaz web de ui/ y un puente a los scripts de bin/ (Python portátil, ffmpeg y el
/// transcriptor vienen dentro de la app). Los videos y proyectos viven en ~/Corta, fuera de la app: actualizar nunca borra nada.
@main
@MainActor
final class CortaApp: NSObject, NSApplicationDelegate {
    static func main() {
        let app = NSApplication.shared
        let delegado = CortaApp()
        app.delegate = delegado
        app.setActivationPolicy(.regular)
        app.run()
    }

    private static var tareasIniciadas = false

    func applicationDidFinishLaunching(_ aviso: Notification) {
        Menu.instalar()
        // Pieza «catálogo»: repo y tipos (efectos y plantillas) salen de app.json; los scripts los corre Procesador.
        Catalogo.configurar(appJSON: Rutas.recursos.appendingPathComponent("app.json"), agente: "Corta/\(Actualizaciones.version)") { s, a, d, fin in
            Procesador.conEntrada(s, a, d, fin: fin)
        }
        Ventana.shared.mostrar()
        // En el primer uso lo primero es elegir el idioma: lo que corre solo y puede mostrar algo (actualizaciones) espera a que
        // esté elegido. Ventana lo llama al guardarse idioma_ui.
        if Idioma.elegido { CortaApp.iniciarTareas() }
    }

    /// Lo que corre solo: revisar actualizaciones al abrir y cada 6 horas. Una sola vez.
    static func iniciarTareas() {
        guard !tareasIniciadas else { return }
        tareasIniciadas = true
        Actualizaciones.revisarCadaRato()
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        Ventana.shared.mostrar()
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
}

/// Barra de menú mínima: la app (Acerca de, Ajustes, Salir), Archivo (video nuevo), Edición (copiar y pegar en la interfaz) y Ventana.
@MainActor
enum Menu {
    static func instalar() {
        let principal = NSMenu()
        let app = NSMenuItem()
        let menuApp = NSMenu()
        menuApp.addItem(withTitle: Idioma.t("Acerca de Corta"), action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        menuApp.addItem(.separator())
        let ajustes = NSMenuItem(title: Idioma.t("Ajustes…"), action: #selector(Ventana.abrirAjustes), keyEquivalent: ",")
        ajustes.target = Ventana.shared
        menuApp.addItem(ajustes)
        menuApp.addItem(.separator())
        menuApp.addItem(withTitle: Idioma.t("Ocultar Corta"), action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        menuApp.addItem(withTitle: Idioma.t("Salir de Corta"), action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        app.submenu = menuApp
        principal.addItem(app)

        let archivo = NSMenuItem()
        let menuArchivo = NSMenu(title: Idioma.t("Archivo"))
        let nuevo = NSMenuItem(title: Idioma.t("Nuevo video…"), action: #selector(Ventana.nuevoVideo), keyEquivalent: "o")
        nuevo.target = Ventana.shared
        menuArchivo.addItem(nuevo)
        let carpeta = NSMenuItem(title: Idioma.t("Abrir la carpeta de tus videos"), action: #selector(Ventana.abrirCarpetaDatos), keyEquivalent: "")
        carpeta.target = Ventana.shared
        menuArchivo.addItem(carpeta)
        archivo.submenu = menuArchivo
        principal.addItem(archivo)

        let edicion = NSMenuItem()
        let menuEdicion = NSMenu(title: Idioma.t("Edición"))
        menuEdicion.addItem(withTitle: Idioma.t("Deshacer"), action: Selector(("undo:")), keyEquivalent: "z")
        menuEdicion.addItem(withTitle: Idioma.t("Rehacer"), action: Selector(("redo:")), keyEquivalent: "Z")
        menuEdicion.addItem(.separator())
        menuEdicion.addItem(withTitle: Idioma.t("Cortar"), action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        menuEdicion.addItem(withTitle: Idioma.t("Copiar"), action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        menuEdicion.addItem(withTitle: Idioma.t("Pegar"), action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        menuEdicion.addItem(withTitle: Idioma.t("Seleccionar todo"), action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        edicion.submenu = menuEdicion
        principal.addItem(edicion)

        let ventana = NSMenuItem()
        let menuVentana = NSMenu(title: Idioma.t("Ventana"))
        menuVentana.addItem(withTitle: Idioma.t("Minimizar"), action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        menuVentana.addItem(withTitle: Idioma.t("Cerrar"), action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        ventana.submenu = menuVentana
        principal.addItem(ventana)
        NSApp.windowsMenu = menuVentana
        NSApp.mainMenu = principal
    }
}
