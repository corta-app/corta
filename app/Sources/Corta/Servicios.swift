import AppKit

// MARK: - Rutas y configuración (compartidas con bin/proyecto.py)

enum Rutas {
    /// Videos y proyectos de la persona: fuera de la app, así actualizar no borra nada.
    static var base: URL { FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Corta") }
    static var interno: URL { base.appendingPathComponent(".corta") }
    static var config: URL { interno.appendingPathComponent("config.json") }
    static var modelos: URL { interno.appendingPathComponent("modelos") }
    /// Código (bin/, ui/, estilos/): dentro de Corta.app.
    static var recursos: URL { Bundle.main.resourceURL!.appendingPathComponent("corta") }
    static var python: URL { Bundle.main.resourceURL!.appendingPathComponent("python/bin/python3") }
    /// ffmpeg, ffprobe y corta-transcribir: junto al ejecutable de la app (Contents/MacOS), verificados por huella al empaquetar.
    static var programas: URL { Bundle.main.executableURL!.deletingLastPathComponent() }

    /// ~/Corta sin enlaces simbólicos, terminada en «/», para comparar rutas.
    static var baseReal: String { base.resolvingSymlinksInPath().path + "/" }

    /// La carpeta de un proyecto que manda la interfaz: tiene que ser una carpeta directa de ~/Corta con su proyecto.json.
    /// (bin/proyecto.py `carpeta_valida` lo revisa otra vez.) Devuelve la ruta real o nil.
    static func proyecto(_ valor: Any?) -> String? {
        guard let s = valor as? String, s.hasPrefix("/"), !s.contains("\u{0}") else { return nil }
        let real = URL(fileURLWithPath: s).standardizedFileURL.resolvingSymlinksInPath()
        guard real.deletingLastPathComponent().path + "/" == baseReal, !real.lastPathComponent.hasPrefix("."),
              FileManager.default.fileExists(atPath: real.appendingPathComponent("proyecto.json").path) else { return nil }
        return real.path
    }

    /// Un archivo dentro de ~/Corta (para «Mostrar en la carpeta»), o nil.
    static func dentro(_ valor: Any?) -> URL? {
        guard let s = valor as? String, s.hasPrefix("/"), !s.contains("\u{0}") else { return nil }
        let real = URL(fileURLWithPath: s).standardizedFileURL.resolvingSymlinksInPath()
        guard real.path.hasPrefix(baseReal), FileManager.default.fileExists(atPath: real.path) else { return nil }
        return real
    }
}

enum Archivos {
    static func leerJSON(_ url: URL) -> [String: Any] {
        guard let d = try? Data(contentsOf: url), let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return [:] }
        return j
    }

    static func escribirJSON(_ url: URL, _ valor: Any) {
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        if let d = try? JSONSerialization.data(withJSONObject: valor, options: [.prettyPrinted, .sortedKeys]) { try? d.write(to: url, options: .atomic) }
    }
}

enum Config {
    static func leer() -> [String: Any] { Archivos.leerJSON(Rutas.config) }

    /// Los mismos ids que IA.conocidas y Modelos.lista (aquí sin depender del hilo principal).
    static let ias: Set<String> = ["claude", "codex", "gemini"]
    static let modelos: Set<String> = ["turbo", "small"]

    /// Solo claves conocidas con valores conocidos: lo que manda la interfaz no puede escribir cualquier cosa.
    static func guardar(_ cambios: [String: Any]) {
        var d = leer()
        for (k, v) in cambios {
            switch k {
            case "ia": if let s = v as? String, ias.contains(s) { d[k] = s }
            case "idioma_ui": if let s = v as? String, s == "es" || s == "en" { d[k] = s }
            case "modelo": if let s = v as? String, modelos.contains(s) { d[k] = s }
            case "idioma_audio":
                if let s = v as? String, s == "auto" || s.range(of: "^[a-z]{2,3}$", options: .regularExpression) != nil { d[k] = s }
            case "bienvenida": if let b = v as? Bool { d[k] = b }
            case "tema": if let s = v as? String, ["sistema", "claro", "oscuro"].contains(s) { d[k] = s }
            default: break
            }
        }
        Archivos.escribirJSON(Rutas.config, d)
    }

    static func texto(_ clave: String) -> String { (leer()[clave] as? String) ?? "" }
}

// MARK: - Idioma (las claves son el texto en español, igual que en ui/idiomas)

enum Idioma {
    nonisolated(unsafe) private static var cache: (codigo: String, textos: [String: String])?

    static var codigo: String {
        let elegido = Config.texto("idioma_ui")
        if !elegido.isEmpty { return elegido }
        return Locale.preferredLanguages.first?.hasPrefix("es") == true ? "es" : "en"
    }

    /// Ya hay idioma: lo eligió (bienvenida o Ajustes) o terminó la bienvenida (no se le vuelve a preguntar).
    static var elegido: Bool { !Config.texto("idioma_ui").isEmpty || Config.leer()["bienvenida"] as? Bool == true }

    static func t(_ texto: String) -> String {
        let c = codigo
        guard c != "es" else { return texto }
        if cache?.codigo != c {
            let j = Archivos.leerJSON(Rutas.recursos.appendingPathComponent("ui/idiomas/\(c).json"))
            cache = (c, j["textos"] as? [String: String] ?? [:])
        }
        return cache?.textos[texto] ?? texto
    }
}

// MARK: - IA de la persona (se detecta y se prueba, no se configura a mano)

@MainActor
enum IA {
    static let conocidas: [(id: String, nombre: String, comandos: [String])] = [
        ("claude", "Claude", ["claude"]),
        ("codex", "ChatGPT (Codex)", ["codex"]),
        ("gemini", "Gemini", ["agy", "gemini"]),
    ]

    /// La app no hereda el PATH de la terminal: se buscan los CLI donde suelen quedar.
    static func dirs() -> [String] {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        var d = ["/opt/homebrew/bin", "/usr/local/bin", "\(home)/.local/bin", "\(home)/.claude/local", "\(home)/.codex/bin",
                 "\(home)/.npm-global/bin", "\(home)/.volta/bin", "\(home)/.bun/bin", "/usr/bin"]
        let nvm = "\(home)/.nvm/versions/node"
        let versiones = ((try? FileManager.default.contentsOfDirectory(atPath: nvm)) ?? []).sorted { $0.compare($1, options: .numeric) == .orderedDescending }
        d += versiones.map { "\(nvm)/\($0)/bin" }
        return d
    }

    static func buscar(_ comandos: [String]) -> String? {
        for c in comandos {
            if let r = dirs().map({ "\($0)/\(c)" }).first(where: { FileManager.default.isExecutableFile(atPath: $0) }) { return r }
        }
        return nil
    }

    static var paraJS: [[String: Any]] {
        conocidas.map { ["id": $0.id, "nombre": $0.nombre, "instalada": buscar($0.comandos) != nil] }
    }

    /// Prueba real: le pide una palabra. Así sabemos que está instalada y con la sesión iniciada. La corre bin/ia.py (pieza «ia»),
    /// con las mismas protecciones que cuando edita: la IA va en un archivo de entrada ({"ia": id}), nunca como argumento.
    /// Responde lo que da `ia.py probar` tal cual ({ia, ok, codigo?, plantilla?, valores?, error?}): la interfaz (pieza «componentes»)
    /// muestra el error traducido con su plantilla y valores.
    static func probar(_ id: String, _ fin: @escaping @MainActor ([String: Any]) -> Void) {
        guard conocidas.contains(where: { $0.id == id }) else { fin(["ia": id, "ok": false, "error": "No conozco esa IA."]); return }
        Procesador.conEntrada("ia.py", "probar", ["ia": id]) { r in
            var x = r
            x["ia"] = id
            if x["ok"] as? Bool != true, x["error"] == nil { x["error"] = "No respondió." }
            fin(x)
        }
    }
}

// MARK: - Modelos de transcripción (whisper.cpp), descargados y verificados por huella (los mismos de Graba y Minuta)

struct ModeloWhisper {
    let id: String, nombre: String, archivo: String, bytes: Int64, sha256: String, detalle: String
}

@MainActor
enum Modelos {
    /// Los nombres de archivo son los que usa bin/importar.py (ARCHIVOS_MODELO). Nombre y detalle se traducen en la interfaz.
    static let lista: [ModeloWhisper] = [
        .init(id: "turbo", nombre: "Preciso", archivo: "ggml-large-v3-turbo-q5_0.bin", bytes: 574_041_195,
              sha256: "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2", detalle: "Mejor para cualquier idioma. 574 MB."),
        .init(id: "small", nombre: "Rápido", archivo: "ggml-small-q5_1.bin", bytes: 190_085_487,
              sha256: "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb", detalle: "Más liviano, un poco menos preciso. 190 MB."),
    ]

    static func existe(_ m: ModeloWhisper) -> Bool {
        let a = (try? FileManager.default.attributesOfItem(atPath: Rutas.modelos.appendingPathComponent(m.archivo).path))?[.size] as? Int64
        return a == m.bytes
    }

    static var hayAlguno: Bool { lista.contains(where: existe) }

    static var recomendado: String { ProcessInfo.processInfo.physicalMemory >= 8 << 30 ? "turbo" : "small" }

    static var paraJS: [String: Any] {
        ["recomendado": recomendado,
         "lista": lista.map { ["id": $0.id, "nombre": $0.nombre, "mb": Int($0.bytes / 1_000_000), "detalle": $0.detalle, "listo": existe($0)] }]
    }

    private static var descarga: Descarga?
    private static var ultimoPct = -1

    static func descargar(_ id: String, progreso: @escaping @MainActor (Double) -> Void, fin: @escaping @MainActor (Bool, String?) -> Void) {
        guard let m = lista.first(where: { $0.id == id }) else { fin(false, Idioma.t("No pude descargar.")); return }
        if existe(m) { fin(true, nil); return }
        guard descarga == nil else { fin(false, Idioma.t("Ya hay una descarga en curso.")); return }
        try? FileManager.default.createDirectory(at: Rutas.modelos, withIntermediateDirectories: true)
        let url = URL(string: "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/\(m.archivo)")!
        ultimoPct = -1
        let d = Descarga(desde: url, sha256: m.sha256, destino: Rutas.modelos.appendingPathComponent(m.archivo),
                         progreso: { bytes in
                             // La interfaz se repinta con cada aviso: solo cuando cambia el porcentaje.
                             let pct = Int(Double(bytes) / Double(m.bytes) * 100)
                             guard pct != Modelos.ultimoPct else { return }
                             Modelos.ultimoPct = pct
                             progreso(min(1, Double(bytes) / Double(m.bytes)))
                         },
                         fin: { ok, error in descarga = nil; fin(ok, error) })
        descarga = d
        d.empezar()
    }
}

/// Descarga a un archivo temporal; solo lo deja en su lugar si la huella SHA-256 coincide.
final class Descarga: NSObject, URLSessionDownloadDelegate, @unchecked Sendable {
    let desde: URL, sha256: String, destino: URL
    let progreso: @MainActor (Int64) -> Void, fin: @MainActor (Bool, String?) -> Void

    init(desde: URL, sha256: String, destino: URL, progreso: @escaping @MainActor (Int64) -> Void, fin: @escaping @MainActor (Bool, String?) -> Void) {
        self.desde = desde; self.sha256 = sha256; self.destino = destino; self.progreso = progreso; self.fin = fin
    }

    func empezar() {
        URLSession(configuration: .default, delegate: self, delegateQueue: nil).downloadTask(with: desde).resume()
    }

    func urlSession(_ s: URLSession, downloadTask: URLSessionDownloadTask, didWriteData _: Int64, totalBytesWritten t: Int64, totalBytesExpectedToWrite _: Int64) {
        Task { @MainActor in self.progreso(t) }
    }

    func urlSession(_ s: URLSession, downloadTask: URLSessionDownloadTask, didFinishDownloadingTo ubicacion: URL) {
        let temporal = destino.appendingPathExtension("descarga")
        try? FileManager.default.removeItem(at: temporal)
        guard (try? FileManager.default.moveItem(at: ubicacion, to: temporal)) != nil else {
            Task { @MainActor in self.fin(false, Idioma.t("No pude guardar la descarga.")) }; return
        }
        let p = Process(), salida = Pipe()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/shasum")
        p.arguments = ["-a", "256", temporal.path]
        p.standardOutput = salida
        try? p.run(); p.waitUntilExit()
        let huella = String(data: salida.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?.split(separator: " ").first.map(String.init) ?? ""
        guard huella == sha256 else {
            try? FileManager.default.removeItem(at: temporal)
            Task { @MainActor in self.fin(false, Idioma.t("La descarga llegó dañada. Intenta de nuevo.")) }; return
        }
        try? FileManager.default.removeItem(at: destino)
        let ok = (try? FileManager.default.moveItem(at: temporal, to: destino)) != nil
        Task { @MainActor in self.fin(ok, ok ? nil : Idioma.t("No pude guardar la descarga.")) }
        s.finishTasksAndInvalidate()
    }

    func urlSession(_ s: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard let error else { return }
        Task { @MainActor in self.fin(false, error.localizedDescription) }
        s.finishTasksAndInvalidate()
    }
}

// MARK: - Scripts de bin/ (contrato: el último argumento es la ruta del JSON de salida)

@MainActor
enum Procesador {
    static func correrJSON(_ script: String, _ args: [String], fin: @escaping @MainActor ([String: Any]) -> Void) {
        let salida = FileManager.default.temporaryDirectory.appendingPathComponent("corta-\(UUID().uuidString).json")
        let p = Process()
        p.executableURL = Rutas.python
        p.arguments = [Rutas.recursos.appendingPathComponent("bin/\(script)").path] + args + [salida.path]
        // Nada del entorno con nombre CORTA_* (p. ej. otra carpeta de datos puesta por otro programa) llega a los scripts:
        // solo las rutas de la app, y ffmpeg y el transcriptor que vienen dentro de ella.
        var env = ProcessInfo.processInfo.environment.filter { !$0.key.hasPrefix("CORTA_") }
        env["CORTA_RECURSOS"] = Rutas.recursos.path
        env["CORTA_PROGRAMAS"] = Rutas.programas.path
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONDONTWRITEBYTECODE"] = "1"  // no escribir __pycache__ dentro de la app (rompería su firma)
        p.environment = env
        p.standardInput = FileHandle.nullDevice
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        p.terminationHandler = { _ in
            Task { @MainActor in
                let r = Archivos.leerJSON(salida)
                try? FileManager.default.removeItem(at: salida)
                fin(r.isEmpty ? ["ok": false, "error": Idioma.t("No pude terminar. Intenta de nuevo.")] : r)
            }
        }
        do { try p.run() } catch { fin(["ok": false, "error": error.localizedDescription]); return }
    }

    /// Igual que correrJSON, pero lo que manda la interfaz va en un archivo de entrada (nada de armar comandos con su texto).
    static func conEntrada(_ script: String, _ accion: String, _ datos: [String: Any], fin: @escaping @MainActor ([String: Any]) -> Void) {
        let entrada = FileManager.default.temporaryDirectory.appendingPathComponent("corta-entrada-\(UUID().uuidString).json")
        Archivos.escribirJSON(entrada, datos)
        correrJSON(script, [accion, entrada.path]) { r in
            try? FileManager.default.removeItem(at: entrada)
            fin(r)
        }
    }
}

/// Los cambios a un proyecto (guardar, deshacer, limpiar, música) corren de a uno y en el orden en que llegaron:
/// así «deshacer» justo después de cortar una palabra deshace ese corte y no otro.
@MainActor
enum EnOrden {
    typealias Tarea = @MainActor (@escaping @MainActor () -> Void) -> Void
    private static var cola: [Tarea] = []
    private static var ocupado = false

    static func agregar(_ tarea: @escaping Tarea) {
        cola.append(tarea)
        siguiente()
    }

    private static func siguiente() {
        guard !ocupado, !cola.isEmpty else { return }
        ocupado = true
        let t = cola.removeFirst()
        t {
            ocupado = false
            siguiente()
        }
    }
}
