using System;
using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using vba_brain.Domain.Common;
using vba_brain.Domain.Interfaces;
using vba_brain.Infrastructure.Persistence;
using vba_brain.Infrastructure.Persistence.Repositories;
using vba_brain.Application.Services;
using vba_brain.UI.Avalonia.ViewModels;
using vba_brain.UI.Avalonia.Views;
using vba_brain.UI.Avalonia.Services;

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
            var mainWindowViewModel = Services.GetRequiredService<MainWindowViewModel>();
            var navigationService = Services.GetRequiredService<INavigationService>();
            navigationService.Setup(mainWindowViewModel);

            // Set initial page to Login
            navigationService.NavigateTo<LoginViewModel>();

            desktop.MainWindow = new MainWindow
            {
                DataContext = mainWindowViewModel
            };
        }

        base.OnFrameworkInitializationCompleted();
    }

    private void ConfigureServices(IServiceCollection services)
    {
        // 1. Build Configuration
        var config = new ConfigurationBuilder()
            .SetBasePath(AppDomain.CurrentDomain.BaseDirectory)
            .AddJsonFile("appsettings.json", optional: false, reloadOnChange: true)
            .Build();

        services.AddSingleton<IConfiguration>(config);

        // 2. Parse DB Config and register DbConnectionFactory
        var providerStr = config["DatabaseConfig:Provider"] ?? "PostgreSQL";
        var connStr = config["DatabaseConfig:ConnectionString"] ?? "";
        
        if (!Enum.TryParse<DatabaseType>(providerStr, true, out var dbType))
        {
            dbType = DatabaseType.PostgreSQL;
        }

        services.AddSingleton<IDbConnectionFactory>(new DbConnectionFactory(connStr, dbType));

        // 3. Register Repositories
        services.AddTransient<IAfterMainRepository, AfterMainRepository>();
        services.AddTransient<IPaymentRepository, PaymentRepository>();
        services.AddTransient<IPrintRepository, PrintRepository>();
        services.AddTransient<IAnalyticsRepository, AnalyticsRepository>();

        // 4. Register Services
        services.AddTransient<IAfterMainService, AfterMainService>();
        services.AddTransient<IPaymentService, PaymentService>();
        services.AddTransient<IPrintService, PrintService>();
        services.AddTransient<IAnalyticsService, AnalyticsService>();

        // 5. Register Navigation Service
        services.AddSingleton<INavigationService, NavigationService>();
        services.AddSingleton<Func<Type, ViewModelBase>>(provider => 
            type => (ViewModelBase)provider.GetRequiredService(type));

        // 6. Register ViewModels
        services.AddSingleton<MainWindowViewModel>();
        services.AddTransient<LoginViewModel>();
        services.AddTransient<MainViewModel>();
        services.AddTransient<RegistrationViewModel>();
        services.AddTransient<EditViewModel>();
        services.AddTransient<PrintSettingsViewModel>();
        services.AddTransient<AnalyticsViewModel>();
    }
}