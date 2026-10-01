using System.Net.Http;
using System.Text.RegularExpressions;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Jellyfin.Plugin.DepthPosters.Api;

/// <summary>
/// Serves the front-end script and proxies depth data from the depth-posters service,
/// so the browser only ever talks to Jellyfin (same origin, no CORS or mixed content).
/// </summary>
[ApiController]
[AllowAnonymous]
[Route("DepthPosters")]
public class DepthPostersController : ControllerBase
{
    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(30) };
    private static readonly Regex IdPattern = new("^[0-9a-fA-F-]{32,36}$", RegexOptions.Compiled);
    private static readonly Regex NamePattern = new(@"^[\w.-]+$", RegexOptions.Compiled);

    [HttpGet("script.js")]
    public IActionResult Script()
    {
        // A script.override.js next to the plugin's configuration file wins, so the script can be iterated on without a rebuild.
        var configDir = Path.GetDirectoryName(Plugin.Instance?.ConfigurationFilePath) ?? string.Empty;
        var overridePath = Path.Combine(configDir, "script.override.js");
        Stream? stream = System.IO.File.Exists(overridePath)
            ? System.IO.File.OpenRead(overridePath)
            : typeof(Plugin).Assembly.GetManifestResourceStream("Jellyfin.Plugin.DepthPosters.Web.script.js");
        if (stream is null)
        {
            return NotFound();
        }

        Response.Headers.CacheControl = "no-cache";
        return File(stream, "application/javascript");
    }

    /// <summary>Effect settings for the front-end script. The service URL is deliberately not exposed.</summary>
    [HttpGet("config.json")]
    public IActionResult ClientConfig()
    {
        var config = Plugin.Instance?.Configuration ?? new PluginConfiguration();
        Response.Headers.CacheControl = "no-cache";
        return new JsonResult(new
        {
            useLayers = config.UseLayers,
            strength = config.Strength,
            tilt = config.Tilt,
            focus = config.Focus,
        });
    }

    [HttpGet("{itemId}/manifest.json")]
    public Task<IActionResult> Manifest(string itemId) => Proxy(itemId, "manifest.json");

    [HttpGet("{itemId}/{tag}/{name}")]
    public Task<IActionResult> Asset(string itemId, string tag, string name)
        => NamePattern.IsMatch(tag) && NamePattern.IsMatch(name)
            ? Proxy(itemId, $"{tag}/{name}")
            : Task.FromResult<IActionResult>(BadRequest());

    private async Task<IActionResult> Proxy(string itemId, string path)
    {
        if (!IdPattern.IsMatch(itemId))
        {
            return BadRequest();
        }

        var baseUrl = (Plugin.Instance?.Configuration.ServiceUrl ?? string.Empty).TrimEnd('/');
        try
        {
            var response = await Http.GetAsync($"{baseUrl}/depth/{itemId}/{path}", HttpCompletionOption.ResponseHeadersRead, HttpContext.RequestAborted);
            if (!response.IsSuccessStatusCode)
            {
                response.Dispose();
                return StatusCode((int)response.StatusCode);
            }

            if (response.Headers.CacheControl is { } cache)
            {
                Response.Headers.CacheControl = cache.ToString();
            }

            var stream = await response.Content.ReadAsStreamAsync(HttpContext.RequestAborted);
            return File(stream, response.Content.Headers.ContentType?.ToString() ?? "application/octet-stream");
        }
        catch (HttpRequestException)
        {
            return StatusCode(502);
        }
    }
}
