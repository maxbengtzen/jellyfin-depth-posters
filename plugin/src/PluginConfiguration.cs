using MediaBrowser.Model.Plugins;

namespace Jellyfin.Plugin.DepthPosters;

public class PluginConfiguration : BasePluginConfiguration
{
    /// <summary>Base URL of the jellyfin-depth-posters service, as seen from the Jellyfin server.</summary>
    public string ServiceUrl { get; set; } = "http://jellyfin-depth-posters:8000";

    /// <summary>Use inpainted layers when the service has generated them (otherwise the depth map only).</summary>
    public bool UseLayers { get; set; } = true;

    /// <summary>Parallax strength (fraction of the poster width at full depth difference).</summary>
    public double Strength { get; set; } = 0.04;

    /// <summary>Card tilt in degrees.</summary>
    public double Tilt { get; set; } = 6;

    /// <summary>Depth (0 = far, 1 = near) that stays still while the rest moves.</summary>
    public double Focus { get; set; } = 0.45;
}
