# Original desktop launcher dependencies

The compiled Linux launcher comes from Pinyon Shift v0.6.0, revision
`9331e453e9850d0fcc1c1606dee95db834a9d317`, under BSD-2-Clause. Its source,
including the RE:COPILE source-location adapter, is in the package's embedded
source zip. `UPSTREAM-LICENSE` retains its authors and terms.

The self-contained executable was built with .NET SDK 8.0.426 and includes
.NET runtime 8.0.32. The accompanying Microsoft license and third-party notices
are retained here. Build-time SDK files are not redistributed in this package.

Resolved desktop dependencies include:

| Component | Version | License and upstream source |
| --- | --- | --- |
| Avalonia desktop UI, Fluent theme and Inter font wrapper | 11.3.22 | MIT; https://github.com/AvaloniaUI/Avalonia/tree/11.3.22 |
| Avalonia BuildServices (build input) | 11.3.2 | MIT; https://github.com/AvaloniaUI/Avalonia |
| Inter typeface | embedded by Avalonia.Fonts.Inter | SIL OFL 1.1; https://github.com/rsms/inter |
| MicroCom.Runtime | 0.11.0 | MIT; https://github.com/kekekeks/MicroCom |
| Tmds.DBus.Protocol | 0.21.3 | MIT; https://github.com/tmds/Tmds.DBus/tree/8cb04f66c330b64244e996ff68f685f27f7381a0 |
| SkiaSharp and Linux native assets | 2.88.9 | MIT and retained native dependency notices; https://github.com/mono/SkiaSharp |
| HarfBuzzSharp and Linux native assets | 8.3.1.1 | MIT and retained native dependency notices; https://github.com/mono/SkiaSharp |
| System.IO.Pipelines | 8.0.0 | MIT and retained Microsoft notices; https://github.com/dotnet/runtime |

This Linux package does not contain the resolved Windows, macOS or WebAssembly
native assets. Third-party names and licenses are retained without implying
endorsement. The remaining notices in this directory are copied from the
upstream repositories, NuGet packages or .NET distribution.

Notice text retains upstream terms; line endings and trailing whitespace are normalized.
