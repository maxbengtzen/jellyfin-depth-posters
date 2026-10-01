using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json.Linq;

namespace Jellyfin.Plugin.DepthPosters;

/// <summary>Payload the File Transformation plugin hands to <see cref="Patches.IndexHtml"/>.</summary>
public class PatchRequestPayload
{
    [JsonPropertyName("contents")]
    public string? Contents { get; set; }
}

public static class Patches
{
    private const string Marker = "<!-- depth-posters -->";

    public static string IndexHtml(PatchRequestPayload payload)
    {
        var html = payload.Contents ?? string.Empty;
        if (html.Contains(Marker, StringComparison.Ordinal))
        {
            return html;
        }

        var tag = $"{Marker}<script defer src=\"/DepthPosters/script.js?v={typeof(Plugin).Assembly.GetName().Version}\"></script>";
        var at = html.LastIndexOf("</body>", StringComparison.OrdinalIgnoreCase);
        return at < 0 ? html + tag : html.Insert(at, tag);
    }
}

/// <summary>Registers the index.html patch with the File Transformation plugin once all plugins are loaded.</summary>
public class TransformationRegistrar : IHostedService
{
    private readonly ILogger<TransformationRegistrar> _logger;

    public TransformationRegistrar(ILogger<TransformationRegistrar> logger)
    {
        _logger = logger;
    }

    public Task StartAsync(CancellationToken cancellationToken)
    {
        var assembly = AssemblyLoadContext.All
            .SelectMany(c => c.Assemblies)
            .FirstOrDefault(a => a.FullName?.Contains(".FileTransformation", StringComparison.Ordinal) ?? false);
        var register = assembly?.GetType("Jellyfin.Plugin.FileTransformation.PluginInterface")?.GetMethod("RegisterTransformation");
        if (register is null)
        {
            _logger.LogError("Depth Posters needs the File Transformation plugin; the hover effect will not be injected");
            return Task.CompletedTask;
        }

        var payload = new JObject
        {
            ["id"] = "8a2f6c1e-5b43-4d8a-b0c7-2e9d41f6a3c5",
            ["fileNamePattern"] = "index.html",
            ["callbackAssembly"] = typeof(Patches).Assembly.FullName,
            ["callbackClass"] = typeof(Patches).FullName,
            ["callbackMethod"] = nameof(Patches.IndexHtml),
        };
        register.Invoke(null, new object?[] { payload });
        _logger.LogInformation("Depth Posters registered its index.html transformation");
        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken cancellationToken) => Task.CompletedTask;
}
