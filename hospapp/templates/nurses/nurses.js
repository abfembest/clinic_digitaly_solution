 
         <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
                <!--Bootstrap JS-- >
                <script src="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/4.6.2/js/bootstrap.bundle.min.js"></script>
                <!--Select2 JS-- >
                <script src="https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/js/select2.min.js"></script>

       <script>
                        //< !-- VITAL SIGNS FORM JS AND jQuery -->
                    $(document).ready(function () {
                        // Initialize Select2 on the patient selection dropdown
                        $('.vitals-form-container #patient_id').select2({
                            placeholder: 'Search and select a patient...',
                            allowClear: true,
                            width: '100%',
                            theme: 'default',
                            language: {
                                searching: function () {
                                    return 'Searching patients...';
                                },
                                noResults: function () {
                                    return 'No patients found';
                                }
                            }
                        });

                        // Auto-calculate BMI when height and weight are entered
                        function calculateBMI() {
                            const height = parseFloat($('.vitals-form-container #height').val());
                            const weight = parseFloat($('.vitals-form-container #weight').val());

                            if (height && weight && height > 0) {
                                const heightInMeters = height / 100;
                                const bmi = (weight / (heightInMeters * heightInMeters)).toFixed(1);
                                $('.vitals-form-container #bmi').val(bmi);
                            } else {
                                $('.vitals-form-container #bmi').val('');
                            }
                        }

                        // Bind BMI calculation to height and weight inputs
                        $('.vitals-form-container #height, .vitals-form-container #weight').on('input', calculateBMI);

                        // Form validation and enhancement
                        $('.vitals-form-container form').on('submit', function (e) {
                            // Add any additional validation here if needed
                            const patientId = $('.vitals-form-container #patient_id').val();
                            if (!patientId) {
                                e.preventDefault();
                                alert('Please select a patient before submitting.');
                                return false;
                            }
                        });

                        // Add floating label effect
                        $('.vitals-form-container .form-control').on('focus blur', function (e) {
                            $(this).parent().toggleClass('focused', e.type === 'focus' || this.value.length > 0);
                        });
                    });
                        // < !--VITAL SIGNS FORM JS AND jQuery ENDS HERE-- >
                </script>
