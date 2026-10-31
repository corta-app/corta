import AppKit
import PiezaCatalogo
import ImageIO
import UniformTypeIdentifiers
import WebKit

/// Ventana principal: la interfaz web (ui/) dentro de un WKWebView. La interfaz llama `host.enviar(accion, datos)`
/// y la app responde con `window.Corta.<funcion>(json)`. El contrato lo revisa pruebas/contrato.py.
@MainActor
final class Ventana: NSObject, NSWindowDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    static let shared = Ventana()
    private var ventana: NSWindow?
    private var web: VistaWeb?
    private var medios: Medios?
    private var lista = false
    private var pendiente: [String: Any] = [:]
    /// Lo que está corriendo por proyecto («transcribir» o «exportar») y su último avance, para la interfaz.
    private var trabajos: [String: String] = [:]
    private var avance: [String: [String: Any]] = [:]
    private var reloj: Timer?
    private var importando = 0

    static let videos = ["mp4", "mov", "m4v", "webm", "mkv"]
    static let audios = ["mp3", "m4a", "aac", "wav", "ogg", "oga", "opus", "flac"]
    /// Fotos que acepta una plantilla (las de iPhone, HEIC, se pasan a JPEG antes: ffmpeg no siempre las lee).
    static let fotos = ["jpg", "jpeg", "png", "webp", "heic", "heif"]

    func mostrar() {
        if ventana == nil { crear() }
        ventana?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    /// ¿Hay algo que se cortaría si la app se cierra (actualizar)?
    var ocupada: Bool { !trabajos.isEmpty || importando > 0 }

    private func crear() {
        let control = WKUserContentController()
        control.add(self, name: "corta")
        control.addUserScript(WKUserScript(source: "window.CORTA_HOST = 'mac';", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        let conf = WKWebViewConfiguration()
        conf.userContentController = control
        // El video y la música de los proyectos llegan por corta:// (Medios), nunca con acceso de lectura a todo el disco.
        let m = Medios()
        medios = m
        conf.setURLSchemeHandler(m, forURLScheme: Medios.esquema)
        conf.mediaTypesRequiringUserActionForPlayback = []
        // La interfaz lee sus traducciones (ui/idiomas/*.json) con fetch desde los mismos archivos locales.
        conf.preferences.setValue(true, forKey: "allowFileAccessFromFileURLs")
        let w = VistaWeb(frame: NSRect(x: 0, y: 0, width: 1280, height: 800), configuration: conf)
        w.navigationDelegate = self
        let v = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 800),
                         styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView], backing: .buffered, defer: false)
        v.titlebarAppearsTransparent = true
        v.titleVisibility = .hidden
        v.title = "Corta"
        v.minSize = NSSize(width: 900, height: 600)
        let contenedor = NSView(frame: w.frame)
        w.frame = contenedor.bounds
        w.autoresizingMask = [.width, .height]
        contenedor.addSubview(w)
        // La web tapa la barra de título: esta franja de arriba es la que mueve la ventana.
        let franja = FranjaArrastre(frame: NSRect(x: 0, y: contenedor.bounds.height - 12, width: contenedor.bounds.width, height: 12))
        franja.autoresizingMask = [.width, .minYMargin]
        contenedor.addSubview(franja)
        v.contentView = contenedor
        v.delegate = self
        v.isReleasedWhenClosed = false
        v.setFrameAutosaveName("Corta")
        if !v.setFrameUsingName("Corta") { v.center() }
        ventana = v
        web = w
        let ui = Rutas.recursos.appendingPathComponent("ui")
        w.loadFileURL(ui.appendingPathComponent("index.html"), allowingReadAccessTo: ui)
    }

    @objc func abrirAjustes() {
        mostrar()
        web?.evaluateJavaScript("window.Corta && window.Corta._probar(E => { E.ajustes = true })")
    }

    @objc func abrirCarpetaDatos() {
        try? FileManager.default.createDirectory(at: Rutas.base, withIntermediateDirectories: true)
        NSWorkspace.shared.open(Rutas.base)
    }

    @objc func nuevoVideo() {
        mostrar()
        elegirVideo()
    }

    // MARK: Hacia la interfaz

    func llamar(_ funcion: String, _ datos: Any) {
        guard let web, let d = try? JSONSerialization.data(withJSONObject: datos), let json = String(data: d, encoding: .utf8) else { return }
        web.evaluateJavaScript("window.Corta && window.Corta.\(funcion)(\(json))")
    }

    /// El estado completo: lo que hay en ~/Corta (lo lee bin/estado.py) más lo propio de la app.
    func enviarEstado(aviso: String? = nil) {
        if let aviso { pendiente["aviso"] = aviso }
        guard lista else { return }
        Procesador.correrJSON("estado.py", []) { datos in
            var e = datos
            e.removeValue(forKey: "ok"); e.removeValue(forKey: "error")
            e["ias"] = IA.paraJS
            e["modelos"] = Modelos.paraJS
            e["version"] = Actualizaciones.version
            e["carpeta"] = Rutas.base.path.replacingOccurrences(of: FileManager.default.homeDirectoryForCurrentUser.path, with: "~")
            e["actualizacion"] = Actualizaciones.disponible
            e["progreso"] = Ventana.shared.avance
            if e["config"] == nil { e["config"] = Config.leer() }
            if e["proyectos"] == nil { e["proyectos"] = [] }
            e.merge(Ventana.shared.pendiente) { _, nuevo in nuevo }
            Ventana.shared.pendiente = [:]
            Ventana.shared.llamar("estado", e)
        }
    }

    private func avisar(_ texto: String) { enviarEstado(aviso: Idioma.t(texto)) }

    // MARK: Trabajos largos (transcribir y exportar): el avance lo deja bin/ en <carpeta>/estado.json

    private func empezar(_ carpeta: String, _ tipo: String, _ inicial: [String: Any]) {
        trabajos[carpeta] = tipo
        avance[carpeta] = inicial.merging(["carpeta": carpeta]) { a, _ in a }
        llamar("progreso", avance[carpeta]!)
        guard reloj == nil else { return }
        reloj = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
            Task { @MainActor in Ventana.shared.revisarAvance() }
        }
    }

    private func revisarAvance() {
        for (carpeta, tipo) in trabajos {
            let e = Archivos.leerJSON(URL(fileURLWithPath: carpeta).appendingPathComponent("estado.json"))
            guard !e.isEmpty else { continue }
            var a: [String: Any] = ["carpeta": carpeta, "paso": e["paso"] as? String ?? tipo]
            if let t = e["texto"] as? String { a["texto"] = Idioma.t(t) }
            if let pct = (e["pct"] as? NSNumber)?.intValue { a["pct"] = max(0, min(100, pct)) }
            if NSDictionary(dictionary: a) == NSDictionary(dictionary: avance[carpeta] ?? [:]) { continue }
            avance[carpeta] = a
            // Exportando, solo se mueve la barra del diálogo (sin repintar todo); transcribiendo, la tarjeta «Preparando tu video».
            if tipo == "exportar" { llamar("exportarProgreso", ["carpeta": carpeta, "pct": a["pct"] ?? 0]) } else { llamar("progreso", a) }
        }
    }

    private func terminar(_ carpeta: String) {
        trabajos.removeValue(forKey: carpeta)
        avance.removeValue(forKey: carpeta)
        try? FileManager.default.removeItem(at: URL(fileURLWithPath: carpeta).appendingPathComponent("estado.json"))
        llamar("progreso", ["carpeta": carpeta, "listo": true])
        if trabajos.isEmpty { reloj?.invalidate(); reloj = nil }
    }

    // MARK: Video nuevo (elegido, soltado o desde el menú)

    func elegirVideo() {
        guard let v = ventana else { return }
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.movie, .mpeg4Movie, .quickTimeMovie] + Ventana.videos.compactMap { UTType(filenameExtension: $0) }
        panel.message = Idioma.t("Elige el video que quieres editar")
        panel.beginSheetModal(for: v) { r in
            guard r == .OK, let u = panel.url else { return }
            Task { @MainActor in Ventana.shared.importar(u) }
        }
    }

    /// Copia el video a ~/Corta/<fecha> <nombre>/ (bin/importar.py; el original nunca se toca) y, si ya hay transcriptor, lo transcribe.
    private func importar(_ video: URL) {
        guard Ventana.videos.contains(video.pathExtension.lowercased()) || UTType(filenameExtension: video.pathExtension)?.conforms(to: .movie) == true,
              FileManager.default.isReadableFile(atPath: video.path) else { return avisar("Elige un video MP4, MOV o WebM.") }
        importando += 1
        avisar("Trayendo tu video…")
        Procesador.correrJSON("importar.py", [video.standardizedFileURL.path]) { r in
            Ventana.shared.importando -= 1
            guard r["ok"] as? Bool == true, let carpeta = r["carpeta"] as? String, let p = r["proyecto"] else {
                return Ventana.shared.enviarEstado(aviso: Idioma.t(r["error"] as? String ?? "No pude traer ese video."))
            }
            Ventana.shared.llamar("proyectoActualizado", ["carpeta": carpeta, "proyecto": p, "seleccionar": true])
            if Modelos.hayAlguno { Ventana.shared.transcribir(carpeta) }
        }
    }

    private func transcribir(_ carpeta: String) {
        guard trabajos[carpeta] == nil else { return }
        guard Modelos.hayAlguno else { return avisar("Primero descarga el transcriptor en Ajustes.") }
        empezar(carpeta, "transcribir", ["paso": "audio", "texto": Idioma.t("Preparando el audio…")])
        Procesador.correrJSON("importar.py", ["transcribir", carpeta]) { r in
            Ventana.shared.terminar(carpeta)
            if r["ok"] as? Bool == true, let p = r["proyecto"] {
                let n = (r["corregidas"] as? NSNumber)?.intValue ?? 0
                let aviso = n > 0 ? Idioma.t("Transcripción lista. Corregí {n} palabras con tu vocabulario.").replacingOccurrences(of: "{n}", with: String(n))
                    : Idioma.t("Transcripción lista")
                Ventana.shared.llamar("proyectoActualizado", ["carpeta": carpeta, "proyecto": p, "aviso": aviso])
            } else {
                Ventana.shared.enviarEstado(aviso: Idioma.t(r["error"] as? String ?? "No pude transcribir."))
            }
        }
    }

    // MARK: Plantillas

    private func panelClips(multiple: Bool) -> NSOpenPanel {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = multiple
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.movie, .image] + (Ventana.videos + Ventana.fotos).compactMap { UTType(filenameExtension: $0) }
        return panel
    }

    /// Corre bin/plantillas.py (crear, ajustar o cambiar) con los archivos elegidos y responde `plantillaArmada`. Las fotos HEIC se
    /// pasan antes a JPEG en una carpeta temporal (se borra al terminar). Mientras arma, la app cuenta como ocupada.
    private func armarPlantilla(_ datos: [String: Any], _ urls: [URL]) {
        var x = datos
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("corta-clips-\(UUID().uuidString)")
        var rutas: [String] = []
        for u in urls.map(\.standardizedFileURL) {
            let ext = u.pathExtension.lowercased()
            if ext == "heic" || ext == "heif" {
                guard let jpg = Ventana.aJPEG(u, en: tmp) else { return llamar("plantillaArmada", ["ok": false, "error": Idioma.t("No pude leer esa foto.")]) }
                rutas.append(jpg.path)
            } else {
                rutas.append(u.path)
            }
        }
        if x["accion"] as? String == "crear" { x["archivos"] = rutas } else if let r = rutas.first { x["archivo"] = r }
        importando += 1
        EnOrden.agregar { listo in
            Procesador.conEntrada("plantillas.py", "entrada", x) { r in
                try? FileManager.default.removeItem(at: tmp)
                Ventana.shared.importando -= 1
                var y = r
                if r["ok"] as? Bool != true { y["error"] = Idioma.t(r["error"] as? String ?? "No pude armar el video.") }
                Ventana.shared.llamar("plantillaArmada", y)
                listo()
            }
        }
    }

    /// Una foto HEIC/HEIF como JPEG (ImageIO, con su orientación aplicada), en `carpeta`.
    private static func aJPEG(_ u: URL, en carpeta: URL) -> URL? {
        try? FileManager.default.createDirectory(at: carpeta, withIntermediateDirectories: true)
        let destino = carpeta.appendingPathComponent(u.deletingPathExtension().lastPathComponent + "-\(UUID().uuidString.prefix(6)).jpg")
        let opciones: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true, kCGImageSourceCreateThumbnailWithTransform: true,
                                         kCGImageSourceThumbnailMaxPixelSize: 4096]
        guard let fuente = CGImageSourceCreateWithURL(u as CFURL, nil),
              let imagen = CGImageSourceCreateThumbnailAtIndex(fuente, 0, opciones as CFDictionary),
              let salida = CGImageDestinationCreateWithURL(destino as CFURL, UTType.jpeg.identifier as CFString, 1, nil) else { return nil }
        CGImageDestinationAddImage(salida, imagen, [kCGImageDestinationLossyCompressionQuality: 0.92] as CFDictionary)
        return CGImageDestinationFinalize(salida) ? destino : nil
    }

    // MARK: Navegación: la ventana solo muestra la interfaz que viene dentro de la app

    /// Carpeta ui/ dentro de la app (sin enlaces simbólicos), para comparar rutas.
    private var carpetaUI: String { Rutas.recursos.appendingPathComponent("ui").resolvingSymlinksInPath().path + "/" }

    /// Un enlace o una redirección nunca carga una página de internet dentro de la ventana (esa página tendría el puente con la app):
    /// solo se permiten los archivos de ui/. Un enlace https que la persona toca se abre en su navegador.
    func webView(_ webView: WKWebView, decidePolicyFor accion: WKNavigationAction) async -> WKNavigationActionPolicy {
        guard let u = accion.request.url else { return .cancel }
        if u.isFileURL, u.resolvingSymlinksInPath().path.hasPrefix(carpetaUI) { return .allow }
        if u.scheme == "https", accion.navigationType == .linkActivated { NSWorkspace.shared.open(u) }
        return .cancel
    }

    // MARK: Desde la interfaz

    func userContentController(_ c: WKUserContentController, didReceive mensaje: WKScriptMessage) {
        // Solo la interfaz local (el marco principal, un archivo de ui/: la navegación de arriba no deja cargar otra cosa) puede
        // pedirle cosas a la app; una página de internet o un iframe, nunca.
        guard mensaje.frameInfo.isMainFrame, mensaje.frameInfo.securityOrigin.protocol == "file" else { return }
        guard let m = mensaje.body as? [String: Any], let accion = m["accion"] as? String else { return }
        let d = m["datos"] as? [String: Any] ?? [:]
        // Toda carpeta que manda la interfaz tiene que ser un proyecto de ~/Corta (bin/ lo vuelve a revisar).
        let carpeta = Rutas.proyecto(d["carpeta"])
        switch accion {
        case "listo":
            lista = true
            enviarEstado()
        case "config":
            Config.guardar(d)
            if d["idioma_ui"] != nil {
                // Los menús se rearman en el idioma nuevo.
                Menu.instalar()
            }
            // Primer uso: recién elegido el idioma, parte lo que esperaba (revisar actualizaciones).
            if Idioma.elegido { CortaApp.iniciarTareas() }
        case "guardarProyecto":
            guard let carpeta, let p = d["proyecto"] as? [String: Any] else { return }
            EnOrden.agregar { listo in
                Procesador.conEntrada("guardar.py", "proyecto", ["carpeta": carpeta, "proyecto": p]) { r in
                    // La interfaz ya pintó el cambio; si no se pudo guardar, se recarga lo que hay en disco y se avisa.
                    if r["ok"] as? Bool != true { Ventana.shared.enviarEstado(aviso: Idioma.t(r["error"] as? String ?? "No pude guardar.")) }
                    listo()
                }
            }
        case "deshacer":
            guard let carpeta else { return }
            EnOrden.agregar { listo in
                Procesador.conEntrada("guardar.py", "deshacer", ["carpeta": carpeta]) { r in
                    if r["ok"] as? Bool == true, let p = r["proyecto"] {
                        let aviso = r["deshecho"] as? Bool == true ? "Deshecho" : "No hay nada que deshacer"
                        Ventana.shared.llamar("proyectoActualizado", ["carpeta": carpeta, "proyecto": p, "aviso": Idioma.t(aviso)])
                    }
                    listo()
                }
            }
        case "elegirVideo":
            elegirVideo()
        case "soltarVideo":
            // La interfaz solo sabe los nombres; las rutas las guardó VistaWeb al soltar (nunca se arma una ruta con lo que manda la web).
            let nombres = Set(d["nombres"] as? [String] ?? [])
            guard let u = web?.soltados.first(where: { nombres.contains($0.lastPathComponent) && Ventana.videos.contains($0.pathExtension.lowercased()) }) else {
                return avisar("Suelta un video MP4, MOV o WebM.")
            }
            web?.soltados = []
            importar(u)
        case "transcribir":
            guard let carpeta else { return }
            transcribir(carpeta)
        case "limpiar":
            guard let carpeta else { return llamar("limpiado", ["ok": false, "error": Idioma.t("No encontré ese proyecto.")]) }
            let silencio = min(5, max(0.2, (d["silencio"] as? NSNumber)?.doubleValue ?? 0.5))
            let muletillas = d["muletillas"] as? Bool ?? true
            EnOrden.agregar { listo in
                Procesador.correrJSON("limpiar.py", [carpeta, String(format: "%.2f", locale: Locale(identifier: "en_US_POSIX"), silencio), muletillas ? "1" : "0"]) { r in
                    Ventana.shared.llamar("limpiado", r)
                    listo()
                }
            }
        case "pedirIA":
            guard let carpeta else { return llamar("iaRespondio", ["ok": false, "error": Idioma.t("No encontré ese proyecto.")]) }
            // El pedido va en un archivo de entrada, nunca como argumento (se vería en la lista de procesos).
            let texto = String((d["texto"] as? String ?? "").prefix(2000))
            Procesador.conEntrada("editar_ia.py", "entrada", ["accion": "pedir", "carpeta": carpeta, "texto": texto]) { Ventana.shared.llamar("iaRespondio", $0) }
        case "buscarShorts":
            guard let carpeta else { return llamar("shortsListos", ["ok": false, "error": Idioma.t("No encontré ese proyecto.")]) }
            Procesador.conEntrada("editar_ia.py", "entrada", ["accion": "shorts", "carpeta": carpeta]) { Ventana.shared.llamar("shortsListos", $0) }
        case "crearShort":
            guard let carpeta, let desde = (d["desde"] as? NSNumber)?.doubleValue, let hasta = (d["hasta"] as? NSNumber)?.doubleValue else { return }
            let titulo = String((d["titulo"] as? String ?? "").prefix(80))
            Procesador.conEntrada("editar_ia.py", "entrada", ["accion": "crear_short", "carpeta": carpeta, "desde": desde, "hasta": hasta, "titulo": titulo]) { r in
                if r["ok"] as? Bool == true, let nueva = r["carpeta"] as? String, let p = r["proyecto"] {
                    Ventana.shared.llamar("proyectoActualizado", ["carpeta": nueva, "proyecto": p, "seleccionar": true, "aviso": Idioma.t("Short creado")])
                } else {
                    Ventana.shared.enviarEstado(aviso: Idioma.t(r["error"] as? String ?? "No pude crear el Short."))
                }
            }
        case "exportar":
            guard let carpeta else { return llamar("exportado", ["ok": false, "error": Idioma.t("No encontré ese proyecto.")]) }
            guard trabajos[carpeta] == nil else { return llamar("exportado", ["ok": false, "error": Idioma.t("Espera a que termine lo que está haciendo este video.")]) }
            empezar(carpeta, "exportar", ["paso": "exportando", "pct": 0])
            Procesador.correrJSON("render.py", [carpeta]) { r in
                Ventana.shared.terminar(carpeta)
                var x = r
                if r["ok"] as? Bool != true { x["error"] = Idioma.t(r["error"] as? String ?? "No pude exportar.") }
                Ventana.shared.llamar("exportado", x)
            }
        case "probarIA":
            // Como en todas las apps de la familia (pieza «host-ui»): {ia} → iaProbada {ia, ok, codigo?, plantilla?, valores?, error?}.
            let id = d["ia"] as? String ?? ""
            IA.probar(id) { r in
                if r["ok"] as? Bool == true { Config.guardar(["ia": id]) }
                Ventana.shared.llamar("iaProbada", r)
            }
        case "descargarModelo":
            let id = d["id"] as? String ?? ""
            Modelos.descargar(id, progreso: { Ventana.shared.llamar("modeloProgreso", ["id": id, "pct": $0]) }) { ok, error in
                if ok { Config.guardar(["modelo": id]) }
                Ventana.shared.llamar("modeloListo", ["id": id, "ok": ok, "error": error ?? ""])
            }
        case "elegirMusica":
            guard let carpeta, let v = ventana else { return llamar("musicaElegida", ["ok": false]) }
            let panel = NSOpenPanel()
            panel.allowsMultipleSelection = false
            panel.canChooseDirectories = false
            panel.allowedContentTypes = [.audio] + Ventana.audios.compactMap { UTType(filenameExtension: $0) }
            panel.message = Idioma.t("Elige la música de fondo")
            panel.beginSheetModal(for: v) { r in
                Task { @MainActor in
                    guard r == .OK, let u = panel.url else { return Ventana.shared.llamar("musicaElegida", ["ok": false]) }
                    EnOrden.agregar { listo in
                        Procesador.correrJSON("musica.py", [carpeta, u.standardizedFileURL.path]) { r in
                            var x = r
                            if r["ok"] as? Bool != true { x["error"] = Idioma.t(r["error"] as? String ?? "No pude usar esa música.") }
                            Ventana.shared.llamar("musicaElegida", x)
                            listo()
                        }
                    }
                }
            }
        case "catalogoEfectos":
            // Efectos de la comunidad (pieza «catálogo»): el índice se baja de un dominio fijo y lo valida bin/catalogo.py.
            Catalogo.listar("efectos") { Ventana.shared.llamar("catalogoListo", $0) }
        case "descargarEfecto":
            // El id solo se busca en el último índice validado; la respuesta trae el efecto en «efecto» o {codigo, frase}.
            Catalogo.descargar("efectos", d["id"] as? String ?? "") { Ventana.shared.llamar("efectoDescargado", $0) }
        case "catalogoPlantillas":
            // Plantillas de la comunidad (y el índice de efectos, para ofrecer los que una plantilla usa y la persona no tiene).
            Catalogo.listar("plantillas") { r in
                guard r["ok"] as? Bool == true else { return Ventana.shared.llamar("catalogoPlantillasListo", r) }
                Catalogo.listar("efectos") { e in
                    var x = r
                    x["efectos"] = e["efectos"] ?? [Any]()
                    Ventana.shared.llamar("catalogoPlantillasListo", x)
                }
            }
        case "descargarPlantilla":
            Catalogo.descargar("plantillas", d["id"] as? String ?? "") { Ventana.shared.llamar("plantillaDescargada", $0) }
        case "elegirClips":
            // Una plantilla: la persona elige sus clips o fotos (van a los huecos en orden de nombre) y bin/plantillas.py arma el video.
            let id = d["plantilla"] as? String ?? ""
            let n = max(1, min(20, (d["n"] as? NSNumber)?.intValue ?? 1))
            guard id.range(of: "^[a-z0-9][a-z0-9-]{0,38}[a-z0-9]$", options: .regularExpression) != nil, let v = ventana else {
                return llamar("plantillaArmada", ["ok": false, "error": Idioma.t("No encontré esa plantilla.")])
            }
            let panel = panelClips(multiple: true)
            panel.message = Idioma.t("Elige {n} clips o fotos. Van en orden de nombre; después puedes cambiar cada uno.").replacingOccurrences(of: "{n}", with: String(n))
            panel.beginSheetModal(for: v) { r in
                Task { @MainActor in
                    guard r == .OK, !panel.urls.isEmpty else { return Ventana.shared.llamar("plantillaArmada", ["ok": false]) }
                    let urls = panel.urls.sorted { $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending }
                    Ventana.shared.armarPlantilla(["accion": "crear", "plantilla": id, "idioma": Idioma.codigo], urls)
                }
            }
        case "ajustarHueco":
            guard let carpeta, let hueco = (d["hueco"] as? NSNumber)?.intValue, let desde = (d["desde"] as? NSNumber)?.doubleValue, desde.isFinite else {
                return llamar("plantillaArmada", ["ok": false, "error": Idioma.t("Ese hueco no existe.")])
            }
            armarPlantilla(["accion": "ajustar", "carpeta": carpeta, "hueco": hueco, "desde": desde], [])
        case "cambiarClip":
            guard let carpeta, let hueco = (d["hueco"] as? NSNumber)?.intValue, let v = ventana else {
                return llamar("plantillaArmada", ["ok": false, "error": Idioma.t("Ese hueco no existe.")])
            }
            let panel = panelClips(multiple: false)
            panel.message = Idioma.t("Elige otro clip o foto para este hueco")
            panel.beginSheetModal(for: v) { r in
                Task { @MainActor in
                    guard r == .OK, let u = panel.url else { return Ventana.shared.llamar("plantillaArmada", ["ok": false]) }
                    Ventana.shared.armarPlantilla(["accion": "cambiar", "carpeta": carpeta, "hueco": hueco], [u])
                }
            }
        case "vocabulario":
            // Recordar o quitar palabras del vocabulario (~/Corta/vocabulario.json). El texto va en el archivo de entrada.
            let texto = { (k: String) in String((d[k] as? String ?? "").prefix(60)) }
            let accion = d["accion"] as? String ?? ""
            guard ["agregar", "quitar", "palabra", "quitar_palabra"].contains(accion) else { return }
            EnOrden.agregar { listo in
                Procesador.conEntrada("vocabulario.py", "entrada", ["accion": accion, "de": texto("de"), "a": texto("a"), "palabra": texto("palabra")]) { r in
                    var x = r
                    if r["ok"] as? Bool != true { x["error"] = Idioma.t(r["error"] as? String ?? "No pude guardar.") }
                    Ventana.shared.llamar("vocabularioActualizado", x)
                    listo()
                }
            }
        case "abrirEnlace":
            if let u = URL(string: d["url"] as? String ?? ""), u.scheme == "https" { NSWorkspace.shared.open(u) }
        case "abrirCarpeta":
            // «Mostrar en la carpeta» del video exportado; sin ruta (o una de afuera), la carpeta de tus videos.
            if let u = Rutas.dentro(d["ruta"]) { NSWorkspace.shared.activateFileViewerSelecting([u]) } else { abrirCarpetaDatos() }
        case "buscarActualizacion":
            Actualizaciones.revisar { hay, detalle in
                let sinConexion = detalle == Actualizaciones.sinConexion
                Ventana.shared.llamar("actualizacionRevisada", ["hay": hay, "notas": hay ? detalle : "", "sinConexion": sinConexion])
            }
        case "actualizar":
            // Nunca en medio de una transcripción o una exportación: cerrar la app las cortaría.
            guard !ocupada else {
                llamar("actualizacionProgreso", ["paso": "error", "texto": Idioma.t("Espera a que termine de transcribir o exportar y vuelve a intentarlo.")])
                return
            }
            Actualizaciones.seguir { Ventana.shared.llamar("actualizacionProgreso", $0) }
            Actualizaciones.instalar { ok, error in
                if !ok { Ventana.shared.llamar("actualizacionProgreso", ["paso": "error", "texto": error]) }
            }
        default:
            break
        }
    }
}

/// El WKWebView de la ventana. Al soltar archivos guarda sus rutas (la página solo recibe los nombres) y después deja que la
/// interfaz reciba el «drop» como siempre; ella manda `soltarVideo` con los nombres.
final class VistaWeb: WKWebView {
    var soltados: [URL] = []

    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        let urls = sender.draggingPasteboard.readObjects(forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]) as? [URL] ?? []
        soltados = urls.map(\.standardizedFileURL)
        return super.performDragOperation(sender)
    }
}

/// Franja invisible arriba de la ventana: arrastrar la mueve y el doble clic la agranda, como una barra de título normal.
/// (WKWebView no entiende `-webkit-app-region`.)
final class FranjaArrastre: NSView {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override func mouseDown(with e: NSEvent) {
        if e.clickCount == 2 { window?.performZoom(nil) } else { window?.performDrag(with: e) }
    }
}
