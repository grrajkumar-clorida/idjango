"""
Admin Dashboard Views for Trading System
Using Django Templates + HTMX + Bootstrap + Chart.js
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg
from django.conf import settings
from datetime import datetime, timedelta
import pytz
import json

# Indian timezone - always use this
INDIAN_TZ = pytz.timezone('Asia/Kolkata')

from stocks.models import Strategy, StrategySignal, LiveTrade, RiskLimits, Orders
from stocks.monitoring.performance_tracker import PerformanceTracker
from stocks.monitoring.trade_monitor import TradeMonitor
from stocks.risk.risk_manager import RiskManager
from stocks.utils.timezone_utils import today_indian, now_indian

# Import Nifty PE function
try:
    from coredata.utils.nifty_cache import get_today_nifty_pe
except ImportError:
    # Fallback if module not available
    def get_today_nifty_pe():
        return [0, "N/A"]


def get_admin_context(base_context=None):
    """
    Helper function to add common admin context (like Nifty PE) to all admin views
    
    Args:
        base_context: Existing context dictionary
    
    Returns:
        Context dictionary with Nifty PE added
    """
    if base_context is None:
        base_context = {}
    
    try:
        nifty_pe_data = get_today_nifty_pe()
        base_context['nifty_pe'] = nifty_pe_data
    except Exception as e:
        # If there's an error fetching PE, set to None
        base_context['nifty_pe'] = None
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error fetching Nifty PE: {str(e)}")
    
    return base_context


# Dashboard Overview
def admin_dashboard(request):
    """Main dashboard overview page"""
    # Get active strategies count
    active_strategies = Strategy.objects.filter(enabled=True).count()
    
    # Get open positions count
    open_positions = Orders.objects.filter(status=0).count()  # Assuming 0 = open
    
    # Get today's P/L (Indian timezone)
    now_indian = timezone.now().astimezone(INDIAN_TZ)
    today = now_indian.date()
    today_trades = Orders.objects.filter(created_at__date=today)
    today_pnl = sum(trade.overall_pl or 0 for trade in today_trades)
    
    # Get total exposure
    total_exposure = Orders.objects.filter(status=0).aggregate(
        total=Sum('invested_value')
    )['total'] or 0
    
    # Performance data for last 7 days (Indian timezone)
    performance_tracker = PerformanceTracker()
    # Get daily performance for last 7 days
    performance_data = []
    now_indian = timezone.now().astimezone(INDIAN_TZ)
    base_date = now_indian.date()
    
    for i in range(7):
        date = base_date - timedelta(days=i)
        daily_perf = performance_tracker.get_daily_performance(date=date)
        performance_data.append(daily_perf)
    
    # Reverse to show oldest to newest
    performance_data.reverse()
    performance_dates = [item['date'].strftime('%Y-%m-%d') for item in performance_data]
    performance_values = [float(item.get('total_pl', 0)) for item in performance_data]
    
    # Strategy distribution
    strategies = Strategy.objects.all()
    strategy_names = [s.name for s in strategies]
    strategy_counts = [StrategySignal.objects.filter(strategy=s).count() for s in strategies]
    
    context = {
        'active_strategies': active_strategies,
        'open_positions': open_positions,
        'today_pnl': today_pnl,
        'total_exposure': total_exposure,
        'performance_dates': json.dumps(performance_dates),
        'performance_values': json.dumps(performance_values),
        'strategy_names': json.dumps(strategy_names),
        'strategy_counts': json.dumps(strategy_counts),
    }
    
    # Add Nifty PE to context
    context = get_admin_context(context)
    
    return render(request, 'stocks/admin_dashboard.html', context)


@require_http_methods(["GET"])
def admin_dashboard_stats(request):
    """HTMX endpoint for dashboard stats refresh"""
    active_strategies = Strategy.objects.filter(enabled=True).count()
    open_positions = Orders.objects.filter(status=0).count()
    
    today = timezone.now().date()
    today_trades = Orders.objects.filter(created_at__date=today)
    today_pnl = sum(trade.overall_pl or 0 for trade in today_trades)
    
    total_exposure = Orders.objects.filter(status=0).aggregate(
        total=Sum('invested_value')
    )['total'] or 0
    
    return HttpResponse(f"""
        <div id="active-strategies">{active_strategies}</div>
        <div id="open-positions">{open_positions}</div>
        <div id="today-pnl">₹{today_pnl:.2f}</div>
        <div id="total-exposure">₹{total_exposure:.2f}</div>
    """)


@require_http_methods(["GET"])
def admin_recent_signals(request):
    """HTMX endpoint for recent signals"""
    recent_signals = StrategySignal.objects.select_related('strategy').order_by('-timestamp')[:10]
    
    html = '<div class="list-group list-group-flush">'
    for signal in recent_signals:
        badge_class = 'success' if signal.signal_type == 'BUY' else 'danger' if signal.signal_type == 'SELL' else 'secondary'
        executed_badge = '<span class="badge badge-success">Executed</span>' if signal.executed else '<span class="badge badge-warning">Pending</span>'
        
        html += f'''
        <div class="list-group-item">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <strong>{signal.stock_code}</strong>
                    <span class="badge badge-{badge_class} ml-2">{signal.signal_type}</span>
                    {executed_badge}
                    <br>
                    <small class="text-muted">{signal.strategy.name} • {signal.timestamp.strftime("%H:%M:%S")}</small>
                </div>
                <div class="text-right">
                    <small>Strength: {signal.strength:.2f}</small>
                </div>
            </div>
        </div>
        '''
    html += '</div>'
    
    if not recent_signals:
        html = '<div class="text-center py-3 text-muted">No recent signals</div>'
    
    return HttpResponse(html)


@require_http_methods(["GET"])
def admin_system_alerts(request):
    """HTMX endpoint for system alerts"""
    risk_manager = RiskManager()
    exposure_data = risk_manager.get_current_exposure()
    
    alerts = []
    
    # Check risk limits
    risk_limits = RiskLimits.objects.first()
    if risk_limits:
        if exposure_data.get('total_exposure', 0) > risk_limits.max_portfolio_exposure:
            alerts.append({
                'type': 'danger',
                'icon': 'exclamation-triangle',
                'message': f"Portfolio exposure ({exposure_data.get('exposure_percent', 0):.1f}%) exceeds limit"
            })
    
    # Check daily loss (Indian timezone)
    now_indian = timezone.now().astimezone(INDIAN_TZ)
    today = now_indian.date()
    today_loss = Orders.objects.filter(created_at__date=today).aggregate(
        total=Sum('overall_pl')
    )['total'] or 0
    
    if risk_limits and today_loss < -abs(risk_limits.max_daily_loss):
        alerts.append({
            'type': 'danger',
            'icon': 'exclamation-circle',
            'message': f"Daily loss ({today_loss:.2f}) approaching limit"
        })
    
    html = '<div class="list-group list-group-flush">'
    for alert in alerts[:5]:  # Show max 5 alerts
        html += f'''
        <div class="list-group-item list-group-item-{alert['type']}">
            <i class="fas fa-{alert['icon']} mr-2"></i>
            {alert['message']}
        </div>
        '''
    html += '</div>'
    
    if not alerts:
        html = '<div class="text-center py-3 text-success"><i class="fas fa-check-circle mr-2"></i>All systems normal</div>'
    
    return HttpResponse(html)


# Strategies Management
def admin_strategies(request):
    """Strategies management page"""
    status_filter = request.GET.get('status', 'all')
    
    context = {
        'status_filter': status_filter,
    }
    
    # Add Nifty PE to context
    context = get_admin_context(context)
    
    return render(request, 'stocks/admin_strategies.html', context)


@require_http_methods(["GET"])
def admin_strategies_table(request):
    """HTMX endpoint for strategies table"""
    status_filter = request.GET.get('status', 'all')
    
    strategies = Strategy.objects.all()
    
    if status_filter == 'enabled':
        strategies = strategies.filter(enabled=True)
    elif status_filter == 'disabled':
        strategies = strategies.filter(enabled=False)
    
    html = '''
    <table class="table table-hover mb-0">
        <thead class="thead-light">
            <tr>
                <th>Strategy Name</th>
                <th>Code</th>
                <th>Status</th>
                <th>Signals</th>
                <th>Created</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
    '''
    
    for strategy in strategies:
        signals_count = StrategySignal.objects.filter(strategy=strategy).count()
        status_badge = 'success' if strategy.enabled else 'secondary'
        status_text = 'Enabled' if strategy.enabled else 'Disabled'
        
        enable_disable_url = f'/stocks/admin/strategies/{strategy.id}/enable/' if not strategy.enabled else f'/stocks/admin/strategies/{strategy.id}/disable/'
        action_text = 'Enable' if not strategy.enabled else 'Disable'
        action_class = 'success' if not strategy.enabled else 'danger'
        
        html += f'''
        <tr>
            <td><strong>{strategy.name}</strong></td>
            <td><code>{strategy.code}</code></td>
            <td><span class="badge badge-{status_badge}">{status_text}</span></td>
            <td>{signals_count}</td>
            <td>{strategy.created_at.strftime("%Y-%m-%d")}</td>
            <td>
                <button class="btn btn-sm btn-{action_class} btn-action"
                        hx-post="{enable_disable_url}"
                        hx-target="#strategies-table"
                        hx-swap="innerHTML"
                        hx-confirm="Are you sure you want to {action_text.lower()} this strategy?">
                    {action_text}
                </button>
                <a href="/stocks/admin/strategies/{strategy.id}/" class="btn btn-sm btn-info btn-action">
                    <i class="fas fa-eye"></i>
                </a>
            </td>
        </tr>
        '''
    
    html += '''
        </tbody>
    </table>
    '''
    
    if not strategies:
        html = '<div class="text-center py-5 text-muted">No strategies found</div>'
    
    return HttpResponse(html)


def admin_strategy_detail(request, strategy_id):
    """View strategy details"""
    strategy = get_object_or_404(Strategy, id=strategy_id)
    
    # Get strategy performance
    performance_tracker = PerformanceTracker()
    performance = performance_tracker.get_strategy_performance(strategy.name, days=30)
    
    # Get recent signals
    recent_signals = StrategySignal.objects.filter(strategy=strategy).order_by('-timestamp')[:20]
    
    # Get statistics
    total_signals = StrategySignal.objects.filter(strategy=strategy).count()
    executed_signals = StrategySignal.objects.filter(strategy=strategy, executed=True).count()
    pending_signals = StrategySignal.objects.filter(strategy=strategy, executed=False).count()
    
    context = {
        'strategy': strategy,
        'performance': performance,
        'recent_signals': recent_signals,
        'total_signals': total_signals,
        'executed_signals': executed_signals,
        'pending_signals': pending_signals,
    }
    
    # Add Nifty PE to context
    context = get_admin_context(context)
    
    return render(request, 'stocks/admin_strategy_detail.html', context)


@require_http_methods(["POST"])
def admin_strategy_enable(request, strategy_id):
    """Enable a strategy"""
    strategy = get_object_or_404(Strategy, id=strategy_id)
    strategy.enabled = True
    strategy.save()
    
    # Return updated table
    return admin_strategies_table(request)


@require_http_methods(["POST"])
def admin_strategy_disable(request, strategy_id):
    """Disable a strategy"""
    strategy = get_object_or_404(Strategy, id=strategy_id)
    strategy.enabled = False
    strategy.save()
    
    # Return updated table
    return admin_strategies_table(request)


# Positions Management
def admin_positions(request):
    """Positions management page"""
    positions = Orders.objects.filter(status=0)  # Open positions
    
    total_positions = positions.count()
    total_pl = sum(p.overall_pl or 0 for p in positions)
    avg_pl_percent = positions.aggregate(avg=Avg('overall_pl'))['avg'] or 0
    
    context = {
        'total_positions': total_positions,
        'total_pl': total_pl,
        'avg_pl_percent': avg_pl_percent,
    }
    
    # Add Nifty PE to context
    context = get_admin_context(context)
    
    return render(request, 'stocks/admin_positions.html', context)


@require_http_methods(["GET"])
def admin_positions_table(request):
    """HTMX endpoint for positions table"""
    positions = Orders.objects.filter(status=0).order_by('-created_at')
    
    html = '''
    <table class="table table-hover mb-0">
        <thead class="thead-light">
            <tr>
                <th>Stock</th>
                <th>Position</th>
                <th>Quantity</th>
                <th>Entry Price</th>
                <th>Current Price</th>
                <th>P/L</th>
                <th>P/L %</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
    '''
    
    for position in positions:
        pl_percent = ((position.overall_pl or 0) / position.invested_value * 100) if position.invested_value else 0
        pl_class = 'success' if (position.overall_pl or 0) >= 0 else 'danger'
        
        html += f'''
        <tr>
            <td><strong>{position.ticker}</strong></td>
            <td><span class="badge badge-info">{position.position}</span></td>
            <td>{position.qty}</td>
            <td>₹{position.price:.2f}</td>
            <td>₹{(position.current_value / float(position.qty)):.2f if position.qty else 0:.2f}</td>
            <td class="text-{pl_class}">₹{position.overall_pl:.2f}</td>
            <td class="text-{pl_class}">{pl_percent:.2f}%</td>
            <td>
                <button class="btn btn-sm btn-danger btn-action"
                        hx-post="/stocks/admin/positions/{position.id}/close/"
                        hx-confirm="Are you sure you want to close this position?">
                    Close
                </button>
            </td>
        </tr>
        '''
    
    html += '''
        </tbody>
    </table>
    '''
    
    if not positions:
        html = '<div class="text-center py-5 text-muted">No open positions</div>'
    
    return HttpResponse(html)


# Performance Page
def admin_performance(request):
    """Performance tracking page"""
    days = int(request.GET.get('days', 30))
    
    performance_tracker = PerformanceTracker()
    # Get daily performance for last N days (Indian timezone)
    daily_performance = []
    now_indian = timezone.now().astimezone(INDIAN_TZ)
    base_date = now_indian.date()
    
    for i in range(days):
        date = base_date - timedelta(days=i)
        daily_perf = performance_tracker.get_daily_performance(date=date)
        daily_performance.append(daily_perf)
    
    # Reverse to show oldest to newest
    daily_performance.reverse()
    
    # Prepare chart data
    dates = [item['date'].strftime('%Y-%m-%d') for item in daily_performance]
    pnl_values = [float(item.get('total_pl', 0)) for item in daily_performance]
    
    # Strategy performance
    strategies = Strategy.objects.all()
    strategy_performance = []
    for strategy in strategies:
        perf = performance_tracker.get_strategy_performance(strategy.name, days=days)
        total_trades = perf.get('total_trades', 0)
        total_pnl = perf.get('total_pnl', 0)
        avg_pnl = (total_pnl / total_trades) if total_trades > 0 else 0
        
        strategy_performance.append({
            'name': strategy.name,
            'total_pnl': total_pnl,
            'win_rate': perf.get('win_rate', 0),
            'total_trades': total_trades,
            'avg_pnl': avg_pnl,
        })
    
    context = {
        'days': days,
        'dates': json.dumps(dates),
        'pnl_values': json.dumps(pnl_values),
        'strategy_performance': strategy_performance,
    }
    
    # Add Nifty PE to context
    context = get_admin_context(context)
    
    return render(request, 'stocks/admin_performance.html', context)


# Risk Management Page
def admin_risk(request):
    """Risk management page"""
    risk_limits = RiskLimits.objects.first()
    if not risk_limits:
        risk_limits = RiskLimits.objects.create()
    
    risk_manager = RiskManager()
    exposure_data = risk_manager.get_current_exposure()
    
    context = {
        'risk_limits': risk_limits,
        'exposure_data': exposure_data,
    }
    
    # Add Nifty PE to context
    context = get_admin_context(context)
    
    return render(request, 'stocks/admin_risk.html', context)


@require_http_methods(["POST"])
def admin_risk_update(request):
    """Update risk limits"""
    risk_limits = RiskLimits.objects.first()
    if not risk_limits:
        risk_limits = RiskLimits.objects.create()
    
    risk_limits.max_position_size = float(request.POST.get('max_position_size', risk_limits.max_position_size))
    risk_limits.max_portfolio_exposure = float(request.POST.get('max_portfolio_exposure', risk_limits.max_portfolio_exposure))
    risk_limits.max_daily_loss = float(request.POST.get('max_daily_loss', risk_limits.max_daily_loss))
    risk_limits.max_drawdown = float(request.POST.get('max_drawdown', risk_limits.max_drawdown))
    risk_limits.save()
    
    return redirect('admin_risk')


@require_http_methods(["GET"])
def admin_risk_alerts(request):
    """HTMX endpoint for risk alerts"""
    risk_manager = RiskManager()
    try:
        exposure_data = risk_manager.get_current_exposure()
    except Exception as e:
        exposure_data = {
            'total_exposure': 0.0,
            'exposure_percent': 0.0,
            'daily_pl': 0.0,
        }
    risk_limits = RiskLimits.objects.first()
    
    alerts = []
    
    if risk_limits:
        # Check portfolio exposure
        if exposure_data.get('exposure_percent', 0) > risk_limits.max_portfolio_exposure:
            alerts.append({
                'type': 'danger',
                'icon': 'exclamation-triangle',
                'message': f"Portfolio exposure ({exposure_data.get('exposure_percent', 0):.1f}%) exceeds limit ({risk_limits.max_portfolio_exposure}%)"
            })
        
        # Check daily loss (Indian timezone)
        now_indian = timezone.now().astimezone(INDIAN_TZ)
        today = now_indian.date()
        today_loss = Orders.objects.filter(created_at__date=today).aggregate(
            total=Sum('overall_pl')
        )['total'] or 0
        
        if today_loss < -abs(risk_limits.max_daily_loss):
            alerts.append({
                'type': 'danger',
                'icon': 'exclamation-circle',
                'message': f"Daily loss (₹{today_loss:.2f}) approaching limit (₹{risk_limits.max_daily_loss:.2f})"
            })
        
        # Check position sizes
        large_positions = Orders.objects.filter(status=0, invested_value__gt=risk_limits.max_position_size)
        if large_positions.exists():
            alerts.append({
                'type': 'warning',
                'icon': 'info-circle',
                'message': f"{large_positions.count()} position(s) exceed max position size"
            })
    
    html = '<div class="list-group list-group-flush">'
    for alert in alerts[:5]:
        html += f'''
        <div class="list-group-item list-group-item-{alert['type']}">
            <i class="fas fa-{alert['icon']} mr-2"></i>
            {alert['message']}
        </div>
        '''
    html += '</div>'
    
    if not alerts:
        html = '<div class="text-center py-3 text-success"><i class="fas fa-check-circle mr-2"></i>All risk parameters within limits</div>'
    
    return HttpResponse(html)


def admin_strategy_register(request):
    """Register new strategy page (placeholder)"""
    return HttpResponse("Strategy registration form - To be implemented")


def admin_sitemap(request):
    """Sitemap page showing all available pages"""
    context = get_admin_context()
    return render(request, 'stocks/admin_sitemap.html', context)


def admin_reports(request):
    """Reports page - main reports dashboard"""
    from stocks.reporting.report_generator import ReportGenerator
    
    # Get report type and date from request
    report_type = request.GET.get('type', 'daily')
    date_str = request.GET.get('date', None)
    strategy_id = request.GET.get('strategy', None)
    
    generator = ReportGenerator(strategy_id=int(strategy_id) if strategy_id else None)
    
    context = {
        'report_type': report_type,
        'strategies': Strategy.objects.all(),
        'selected_strategy': int(strategy_id) if strategy_id else None,
    }
    
    # Generate report based on type
    if report_type == 'daily':
        date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else today_indian()
        report = generator.generate_daily_report(date)
        context['report'] = report
        context['selected_date'] = date
    elif report_type == 'weekly':
        week_start_str = request.GET.get('week_start', None)
        if week_start_str:
            week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
        else:
            today = today_indian()
            days_since_monday = today.weekday()
            week_start = today - timedelta(days=days_since_monday)
        report = generator.generate_weekly_report(week_start)
        context['report'] = report
        context['week_start'] = week_start
    elif report_type == 'monthly':
        year = int(request.GET.get('year', now_indian().year))
        month = int(request.GET.get('month', now_indian().month))
        report = generator.generate_monthly_report(year, month)
        context['report'] = report
        context['selected_year'] = year
        context['selected_month'] = month
    else:
        # Default to daily
        report = generator.generate_daily_report()
        context['report'] = report
        context['selected_date'] = today_indian()
    
    # Add Nifty PE to context
    context = get_admin_context(context)
    
    return render(request, 'stocks/admin_reports.html', context)
