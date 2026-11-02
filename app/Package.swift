// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "Corta",
    platforms: [.macOS("15.0")],
    targets: [
        .executableTarget(
            name: "Corta",
            dependencies: ["PiezaHost", "PiezaActualizaciones", "PiezaCatalogo"],
            path: "Sources/Corta"
        ),
        // Piezas de Pieza (no se editan a mano): la app de Mac genérica («host-mac»: ventana, puente, config, idioma, menús, scripts
        // con límite y acciones declaradas en acciones.json), las actualizaciones y el catálogo (Corta lo configura con app.json).
        .target(name: "PiezaHost", path: "Sources/PiezaHost"),
        .target(name: "PiezaActualizaciones", path: "Sources/PiezaActualizaciones"),
        .target(name: "PiezaCatalogo", path: "Sources/PiezaCatalogo"),
        // whisper.cpp oficial (framework para Apple, usa Metal). La misma versión y huella que Graba y Minuta.
        .binaryTarget(
            name: "whisper",
            url: "https://github.com/ggml-org/whisper.cpp/releases/download/v1.8.3/whisper-v1.8.3-xcframework.zip",
            checksum: "a970006f256c8e689bc79e73f7fa7ddb8c1ed2703ad43ee48eb545b5bb6de6af"
        ),
        .executableTarget(
            name: "corta-transcribir",
            dependencies: ["whisper"],
            path: "Sources/Transcribir",
            linkerSettings: [.unsafeFlags(["-Xlinker", "-rpath", "-Xlinker", "@executable_path/../Frameworks",
                                           "-Xlinker", "-rpath", "-Xlinker", "@executable_path"])]
        ),
    ]
)
