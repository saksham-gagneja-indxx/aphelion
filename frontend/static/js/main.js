/**
 * Social Media Automation Dashboard - Main JS
 * Handles all client-side interactions
 */

// API Base URL
const API_BASE = '/api';

// User ID (would be from session in production)
let currentUserId = 1;

// ============ API Helpers ============

/**
 * Make API request
 */
async function apiCall(endpoint, options = {}) {
    try {
        const url = `${API_BASE}${endpoint}`;
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * Show notification
 */
function showNotification(message, type = 'success') {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;

    const container = document.querySelector('main');
    if (container) {
        container.insertAdjacentHTML('afterbegin', alertHtml);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const alert = container.querySelector('.alert');
            if (alert) {
                alert.remove();
            }
        }, 5000);
    }
}

/**
 * Format date and time
 */
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Format time duration
 */
function formatDuration(hours) {
    if (hours < 1) {
        return Math.round(hours * 60) + ' minutes';
    } else if (hours < 24) {
        return Math.round(hours) + ' hours';
    } else {
        return Math.round(hours / 24) + ' days';
    }
}

/**
 * Get badge class for status
 */
function getStatusBadgeClass(status) {
    const classes = {
        'draft': 'badge-draft',
        'queued': 'badge-queued',
        'scheduled': 'badge-scheduled',
        'posted': 'badge-posted',
        'failed': 'badge-failed'
    };
    return classes[status] || 'badge-secondary';
}

// ============ Dashboard Functions ============

/**
 * Load dashboard stats
 */
async function loadDashboardStats() {
    try {
        const data = await apiCall('/stats');

        document.getElementById('total-posts').textContent = data.posts.total;
        document.getElementById('posted-count').textContent = data.posts.posted;
        document.getElementById('scheduled-count').textContent = data.posts.scheduled;
        document.getElementById('pending-count').textContent = data.posts.pending;

        document.getElementById('job-count').textContent = `${data.scheduler.total_jobs} jobs`;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

/**
 * Load recent posts
 */
async function loadRecentPosts() {
    try {
        const data = await apiCall(`/users/${currentUserId}/posts?limit=5`);

        const container = document.getElementById('recent-posts');
        if (!container) return;

        if (data.posts && data.posts.length > 0) {
            container.innerHTML = data.posts.map(post => `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6 class="mb-1">
                                ${post.caption ? post.caption.substring(0, 50) : 'Post #' + post.id}
                            </h6>
                            <p class="text-muted mb-1 small">
                                <span class="badge ${getStatusBadgeClass(post.status)}">${post.status}</span>
                                ${post.posted_at ? ' • Posted ' + formatDateTime(post.posted_at) : ''}
                            </p>
                            <small class="text-muted">
                                👍 ${post.likes || 0} | 💬 ${post.comments || 0} | 👁️ ${post.views || 0}
                            </small>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = `
                <div class="list-group-item">
                    <p class="text-muted mb-0">No posts yet. <a href="/queue">Upload your first reel</a></p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading posts:', error);
    }
}

/**
 * Load optimal time
 */
async function loadOptimalTime() {
    try {
        const data = await apiCall(`/users/${currentUserId}/optimal-time`);
        const container = document.getElementById('optimal-time');

        if (!container) return;

        if (data.optimal_time) {
            const time = new Date(data.optimal_time);
            container.innerHTML = `
                <h4 class="mb-2">${formatDateTime(data.optimal_time)}</h4>
                <p class="text-muted mb-2">
                    ${formatDuration(data.wait_hours)} from now
                </p>
                <div class="progress mb-2" style="height: 1.5rem;">
                    <div class="progress-bar" style="width: ${data.confidence}%">
                        ${data.confidence}% confidence
                    </div>
                </div>
                <small class="text-muted d-block">
                    Best hours: ${data.best_hours.join(', ')} |
                    Best days: ${['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][data.best_days[0]]}
                </small>
            `;
        } else {
            container.innerHTML = `
                <p class="text-muted mb-0">
                    <i class="fas fa-info-circle"></i>
                    No analytics data yet. <a href="/analytics">Analyze engagement</a>
                </p>
            `;
        }
    } catch (error) {
        console.error('Error loading optimal time:', error);
    }
}

// ============ Queue Functions ============

/**
 * Add post to queue
 */
async function addToQueue(postId) {
    try {
        const data = await apiCall('/queue/add', {
            method: 'POST',
            body: JSON.stringify({ post_id: postId })
        });

        showNotification('Post added to queue', 'success');
        loadQueue();
    } catch (error) {
        showNotification('Error adding to queue', 'danger');
    }
}

/**
 * Remove from queue
 */
async function removeFromQueue(postId) {
    if (!confirm('Remove this post from queue?')) return;

    try {
        await apiCall(`/queue/${postId}`, { method: 'DELETE' });
        showNotification('Post removed from queue', 'success');
        loadQueue();
    } catch (error) {
        showNotification('Error removing from queue', 'danger');
    }
}

/**
 * Load queue
 */
async function loadQueue() {
    try {
        const data = await apiCall('/scheduler/pending');
        const container = document.getElementById('queue-list');

        if (!container) return;

        if (data.posts && data.posts.length > 0) {
            container.innerHTML = data.posts.map(post => `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6 class="mb-1">Post #${post.id}</h6>
                            <p class="text-muted mb-1 small">
                                ${post.caption ? post.caption.substring(0, 100) + '...' : 'No caption'}
                            </p>
                            <small class="text-muted">
                                Added ${formatDateTime(post.created_at)}
                            </small>
                        </div>
                        <div class="btn-group" role="group">
                            <button class="btn btn-sm btn-success" onclick="schedulePost(${post.id})">
                                <i class="fas fa-clock"></i> Schedule
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="removeFromQueue(${post.id})">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = `
                <div class="alert alert-info mb-0">
                    <i class="fas fa-info-circle"></i> No posts in queue
                </div>
            `;
        }

        document.getElementById('queue-count').textContent = data.count;
    } catch (error) {
        console.error('Error loading queue:', error);
    }
}

// ============ Scheduling Functions ============

/**
 * Schedule post
 */
async function schedulePost(postId, useOptimal = false) {
    try {
        let data;

        if (useOptimal) {
            data = await apiCall(`/posts/${postId}/schedule-optimal`, {
                method: 'POST'
            });
        } else {
            // Prompt for time
            const timeStr = prompt('Enter scheduled time (YYYY-MM-DD HH:MM):');
            if (!timeStr) return;

            data = await apiCall(`/posts/${postId}/schedule`, {
                method: 'POST',
                body: JSON.stringify({
                    scheduled_time: new Date(timeStr).toISOString()
                })
            });
        }

        if (data.success) {
            showNotification(
                `Post scheduled at ${formatDateTime(data.post.scheduled_time)}`,
                'success'
            );
            loadQueue();
            loadDashboardStats();
        } else {
            showNotification(data.message || 'Failed to schedule post', 'danger');
        }
    } catch (error) {
        showNotification('Error scheduling post', 'danger');
    }
}

// ============ Analytics Functions ============

/**
 * Refresh analytics
 */
async function refreshAnalytics() {
    const btn = document.getElementById('refreshBtn');
    if (!btn) return;

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';

    try {
        const data = await apiCall(`/users/${currentUserId}/analyze`, {
            method: 'POST'
        });

        if (data.success) {
            showNotification('Analytics updated successfully', 'success');
            loadAnalytics();
        } else {
            showNotification('Failed to analyze engagement', 'danger');
        }
    } catch (error) {
        showNotification('Error refreshing analytics', 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh Analytics';
    }
}

/**
 * Load analytics
 */
async function loadAnalytics() {
    try {
        const data = await apiCall(`/users/${currentUserId}/analytics`);

        if (data.total_posts_analyzed) {
            document.getElementById('posts-analyzed').textContent = data.total_posts_analyzed;
            document.getElementById('avg-likes').textContent = Math.round(data.average_likes || 0);
            document.getElementById('avg-comments').textContent = Math.round(data.average_comments || 0);
            document.getElementById('confidence').textContent = Math.round(data.confidence || 0) + '%';
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

// ============ Initialization ============

/**
 * Initialize page based on current route
 */
function initializePage() {
    const path = window.location.pathname;

    if (path.includes('/dashboard') || path === '/') {
        loadDashboardStats();
        loadRecentPosts();
        loadOptimalTime();
    } else if (path.includes('/queue')) {
        loadQueue();
    } else if (path.includes('/analytics')) {
        loadAnalytics();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initializePage);

// Auto-refresh stats every 30 seconds
setInterval(() => {
    if (document.getElementById('total-posts')) {
        loadDashboardStats();
    }
}, 30000);
