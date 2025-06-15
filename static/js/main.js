// 自定义JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // 添加淡入动画效果
    const fadeElements = document.querySelectorAll('.fade-in');
    fadeElements.forEach((el, index) => {
        el.style.opacity = '0';
        setTimeout(() => {
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        }, 100 * index);
    });
    
    // 预约日期限制 - 不能选择过去的日期
    const reservationDateInput = document.getElementById('reservation_date');
    if (reservationDateInput) {
        const today = new Date().toISOString().split('T')[0];
        reservationDateInput.min = today;
    }
    
    // 监听预约日期和时间变化，动态更新可用餐桌
    if (reservationDateInput) {
        const reservationTimeInput = document.getElementById('reservation_time');
        const tableSelect = document.getElementById('table_id');
        
        const updateAvailableTables = () => {
            const date = reservationDateInput.value;
            const time = reservationTimeInput.value;
            
            if (date && time) {
                // 显示加载状态
                tableSelect.innerHTML = '<option value="" disabled>加载中...</option>';
                
                // 发送AJAX请求获取可用餐桌
                fetch(`/api/available-tables?date=${date}&time=${time}`)
                    .then(response => response.json())
                    .then(tables => {
                        tableSelect.innerHTML = '<option value="" disabled selected>请选择餐桌</option>';
                        
                        if (tables.length > 0) {
                            tables.forEach(table => {
                                const option = document.createElement('option');
                                option.value = table.id;
                                option.textContent = `桌号: ${table.table_number} (${table.capacity}人桌, ${table.table_type})`;
                                tableSelect.appendChild(option);
                            });
                        } else {
                            const option = document.createElement('option');
                            option.value = '';
                            option.disabled = true;
                            option.textContent = '该时间段暂无可用餐桌';
                            tableSelect.appendChild(option);
                        }
                    })
                    .catch(error => {
                        console.error('获取可用餐桌失败:', error);
                        tableSelect.innerHTML = '<option value="" disabled>获取可用餐桌失败</option>';
                    });
            }
        };
        
        reservationDateInput.addEventListener('change', updateAvailableTables);
        reservationTimeInput.addEventListener('change', updateAvailableTables);
    }
});
