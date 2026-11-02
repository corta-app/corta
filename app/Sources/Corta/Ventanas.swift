import AppKit
import PiezaHost
import WebKit

/// Lo de la ventana que es de Corta, sobre la de la pieza «host-mac»:
///   · la interfaz llega hasta arriba (barra de título transparente; ui/app.css deja lugar a los botones con
///     `html[data-host="mac"] .barra`) y una franja invisible arriba mueve la ventana (WKWebView no entiende `-webkit-app-region`);
///   · al soltar archivos en la ventana se guardan sus rutas (la página solo recibe los nombres y manda `soltarVideo`): nunca se arma
///     una ruta con lo que manda la web.
/// El host crea la ventana al abrir (después del bloque de `Host.arrancar`): esto se aplica justo después, en la misma vuelta.
@MainActor
enum Ventanas {
    /// Lo último que se soltó en la ventana (rutas reales; la interfaz pide uno por su nombre).
    static var soltados: [URL] = []
    private static var hecho = false

    static func preparar() {
        DispatchQueue.main.async { Task { @MainActor in ajustar() } }
    }

    private static func ajustar() {
        guard !hecho, let v = Puente.shared.ventana, let web = Puente.shared.web else {
            if !hecho { preparar() }  // la ventana todavía no está: otra vuelta
            return
        }
        hecho = true
        v.styleMask.insert(.fullSizeContentView)
        v.titlebarAppearsTransparent = true
        v.titleVisibility = .hidden
        let contenedor = NSView(frame: web.frame)
        v.contentView = contenedor
        web.frame = contenedor.bounds
        web.autoresizingMask = [.width, .height]
        contenedor.addSubview(web)
        let soltar = CapaSoltar(frame: contenedor.bounds, web: web)
        soltar.autoresizingMask = [.width, .height]
        contenedor.addSubview(soltar)
        let franja = FranjaArrastre(frame: NSRect(x: 0, y: contenedor.bounds.height - 12, width: contenedor.bounds.width, height: 12))
        franja.autoresizingMask = [.width, .minYMargin]
        contenedor.addSubview(franja)
    }
}

/// Una capa transparente sobre la interfaz que solo atiende archivos que se sueltan: guarda sus rutas y le pasa todo lo demás al
/// WKWebView (así la página recibe su dragover/drop como siempre). Los clics la atraviesan (`hitTest` devuelve nil).
final class CapaSoltar: NSView {
    private weak var web: WKWebView?

    init(frame: NSRect, web: WKWebView) {
        self.web = web
        super.init(frame: frame)
        registerForDraggedTypes([.fileURL])
    }

    required init?(coder: NSCoder) { nil }

    override func hitTest(_ punto: NSPoint) -> NSView? { nil }
    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation { web?.draggingEntered(sender) ?? [] }
    override func draggingUpdated(_ sender: NSDraggingInfo) -> NSDragOperation { web?.draggingUpdated(sender) ?? [] }
    override func draggingExited(_ sender: NSDraggingInfo?) { web?.draggingExited(sender) }
    override func prepareForDragOperation(_ sender: NSDraggingInfo) -> Bool { web?.prepareForDragOperation(sender) ?? false }
    override func concludeDragOperation(_ sender: NSDraggingInfo?) { web?.concludeDragOperation(sender) }
    override func draggingEnded(_ sender: NSDraggingInfo) { web?.draggingEnded(sender) }

    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        let urls = sender.draggingPasteboard.readObjects(forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]) as? [URL] ?? []
        MainActor.assumeIsolated { Ventanas.soltados = urls.map(\.standardizedFileURL) }
        return web?.performDragOperation(sender) ?? false
    }
}

/// Franja invisible arriba de la ventana: arrastrar la mueve y el doble clic la agranda, como una barra de título normal.
final class FranjaArrastre: NSView {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override func mouseDown(with e: NSEvent) {
        if e.clickCount == 2 { window?.performZoom(nil) } else { window?.performDrag(with: e) }
    }
}
