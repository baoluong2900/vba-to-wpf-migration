using System;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Layout;
using Avalonia.Markup.Xaml;
using Avalonia.Media;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using vba_brain.Domain.Common;
using vba_brain.Infrastructure.Persistence;

namespace vba_brain.UI.Avalonia;

public partial class App : global::Avalonia.Application
{
    public static IServiceProvider? Services { get; private set; }

    public override void Initialize()
    {
        AvaloniaXamlLoader.Load(this);
    }

    public override void OnFrameworkInitializationCompleted()
    {
        var services = new ServiceCollection();
        ConfigureServices(services);
        Services = services.BuildServiceProvider();

        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            // Layer 5 deploys views, view models and services form by form. Until a form's
            // service implementation is registered in ConfigureServices, show what is missing
            // instead of running as an invisible process that never exits.
            desktop.MainWindow = CreatePlaceholderWindow();
        }

        base.OnFrameworkInitializationCompleted();
    }

    private static void ConfigureServices(IServiceCollection services)
    {
        var config = new ConfigurationBuilder()
            .SetBasePath(AppDomain.CurrentDomain.BaseDirectory)
            .AddJsonFile("appsettings.json", optional: true, reloadOnChange: false)
            .Build();
        services.AddSingleton<IConfiguration>(config);

        var providerStr = config["DatabaseConfig:Provider"] ?? "PostgreSQL";
        var connStr = config["DatabaseConfig:ConnectionString"] ?? "";
        if (!Enum.TryParse<DatabaseType>(providerStr, true, out var dbType))
        {
            dbType = DatabaseType.PostgreSQL;
        }
        services.AddSingleton<IDbConnectionFactory>(new DbConnectionFactory(connStr, dbType));
        services.AddSingleton<DapperContext>();

        // Register generated repositories, services, view models and views here as Layer 5
        // deploys them, then create the first view in OnFrameworkInitializationCompleted, e.g.:
        //   services.AddTransient<IFLoginService, FLoginService>();
        //   services.AddTransient<ViewModels.FLoginViewModel>();
        //   services.AddTransient<Views.FLoginView>();
    }

    private static Window CreatePlaceholderWindow() => new()
    {
        Title = "vba_brain",
        Width = 560,
        Height = 220,
        WindowStartupLocation = WindowStartupLocation.CenterScreen,
        Content = new TextBlock
        {
            Margin = new Thickness(24),
            TextWrapping = TextWrapping.Wrap,
            VerticalAlignment = VerticalAlignment.Center,
            Text = "No generated screen is wired up yet.\n\n"
                 + "Run the Layer 5 pipeline (Repo → Service → UI → Logic), then register the "
                 + "generated service, view model and view in App.ConfigureServices and open "
                 + "the first view as the main window.",
        },
    };
}
