import Foundation
import PiezaHost

/// `corta://video/<carpeta>/<archivo>`: el video y la música de un proyecto para la vista previa. Los rangos (Range, para poder
/// adelantar) los sirve la pieza «host-mac» (`registrarMedios("video")`); aquí se decide qué archivo se puede servir, y solo:
///   · el video del proyecto (`fuente.archivo` de su proyecto.json) o un archivo de su carpeta `musica/` o `clips/` (los clips y
///     fotos de una plantilla, para verlos al elegir qué parte va en cada hueco),
///   · de una carpeta directa de ~/Corta con proyecto.json, y
///   · sin enlaces simbólicos que lleven fuera de ~/Corta.
/// Todo lo demás (otra ruta, «..», ~/Corta/.corta, otro esquema, `?` o `#`) no se sirve.
@MainActor
enum Medios {
    static let esquema = "corta"

    /// `ruta` es lo que viene después de `corta://video/`, ya sin la «/» del comienzo (la interfaz manda la ruta absoluta entera,
    /// con encodeURIComponent: `corta://video/%2FUsers%2Fana%2FCorta%2F…`).
    static func archivo(_ ruta: String) -> URL? {
        let absoluta = "/" + ruta
        guard !absoluta.contains("\u{0}") else { return nil }
        let real = URL(fileURLWithPath: absoluta).standardizedFileURL.resolvingSymlinksInPath()
        let base = Rutas.baseReal
        guard real.path.hasPrefix(base) else { return nil }
        let partes = real.path.dropFirst(base.count).split(separator: "/", omittingEmptySubsequences: false).map(String.init)
        guard partes.count == 2 || (partes.count == 3 && ["musica", "clips"].contains(partes[1])),
              let carpeta = partes.first, !carpeta.isEmpty, !carpeta.hasPrefix("."), partes.allSatisfy({ !$0.isEmpty }) else { return nil }
        let p = Archivos.leerJSON(URL(fileURLWithPath: base + carpeta).appendingPathComponent("proyecto.json"))
        guard let fuente = p["fuente"] as? [String: Any] else { return nil }
        if partes.count == 2, partes[1] != (fuente["archivo"] as? String) { return nil }
        var esDirectorio: ObjCBool = false
        guard FileManager.default.fileExists(atPath: real.path, isDirectory: &esDirectorio), !esDirectorio.boolValue else { return nil }
        return real
    }
}
